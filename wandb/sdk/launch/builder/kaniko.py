from kubernetes import client, config
from typing import Optional
import tarfile
import tempfile
import time
import base64
import os
import wandb
import boto3
import botocore

from wandb.docker import run


_DEFAULT_BUILD_TIMEOUT_SECS = 1800  # 30 minute build timeout


def _upload_build_context(run_id: str, context_path: str):
    # creat a tar archive of the build context and upload it to s3
    context_tgz = tempfile.NamedTemporaryFile(delete=False)
    with tarfile.TarFile.open(fileobj=context_tgz, mode="w:gz") as context_tgz:
        context_tgz.add(context_path, arcname=".")

    s3_client = boto3.client("s3")
    try:
        s3_client.upload_file(context_tgz.name, "wandb-build", f"{run_id}.tgz")
    except botocore.exceptions.ClientError as e:
        wandb.termerror(f"Failed to upload build context to S3: {e}")
        return False
    return f"s3://wandb-build/{run_id}.tgz"


def _create_dockerfile_configmap(config_map_name: str, context_path) -> client.V1ConfigMap:
    with open(os.path.join(context_path, "Dockerfile.wandb-autogenerated"), 'rb') as f:
        docker_file_bytes = f.read()

    build_config_map = client.V1ConfigMap(
        metadata=client.V1ObjectMeta(
            name=config_map_name,
            namespace="wandb",
            labels={"wandb": "launch"}
        ),
        binary_data={
            "Dockerfile": base64.b64encode(docker_file_bytes).decode('UTF-8'),
        },
        immutable=True,
    )
    return build_config_map


def _create_kaniko_job(job_name: str, config_map_name: str, registry: str, image_tag: str, build_context_path: str) -> client.V1Job:
    # Configureate Pod template container
    container = client.V1Container(
        name="wandb-container-build",
        image="gcr.io/kaniko-project/executor:debug",
        args=[
            f"--context={build_context_path}",
            "--dockerfile=/etc/config/Dockerfile",
            f"--destination={image_tag}",
            "--cache=true",
            f"--cache-repo={registry}"
        ],
        volume_mounts=[
            client.V1VolumeMount(
                name="build-context-config-map",
                mount_path="/etc/config"
            ),
            # TODO: get credentials via config instead of hardcode
            client.V1VolumeMount(
                name="docker-config",
                mount_path="/kaniko/.docker/"
            ),
            client.V1VolumeMount(
                name="aws-secret",
                mount_path="/root/.aws/"
            ),
        ],
    )
    # Create and configure a spec section
    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"wandb": "launch"}),
        spec=client.V1PodSpec(
            restart_policy="Never",
            active_deadline_seconds=_DEFAULT_BUILD_TIMEOUT_SECS,
            containers=[container],
            volumes=[
                client.V1Volume(
                    name="build-context-config-map",
                    config_map=client.V1ConfigMapVolumeSource(
                        name=config_map_name,
                    )
                ),
                client.V1Volume(
                    name="docker-config",
                    config_map=client.V1ConfigMapVolumeSource(
                        name="docker-config",
                    )
                ),
                client.V1Volume(
                    name="aws-secret",
                    secret=client.V1SecretVolumeSource(
                        secret_name="aws-secret"
                    )
                )
            ]
        )
    )
    # Create the specification of job
    spec = client.V1JobSpec(
        template=template,
        backoff_limit=1)
    job = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(
            name=job_name,
            namespace="wandb",
            labels={"wandb": "launch"}
        ),
        spec=spec)

    return job


def _wait_for_completion(api_client: client.BatchV1Api, job_name: str, deadline_secs: Optional[int] = None) -> bool:
    # TODO: can probably share code here with steph
    start_time = time.time()
    while True:
        job = api_client.read_namespaced_job_status(job_name, "wandb")
        if job.status.succeeded is not None and job.status.succeeded >= 1:
            return True
        elif job.status.failed is not None and job.status.failed >= 1:
            return False
        wandb.termlog("Waiting for build job to complete...")
        if deadline_secs is not None and time.time() - start_time > deadline_secs:
            return False

        time.sleep(5)

    return False


def build_image(run_id: str, registry: str, image_uri: str, context_path: str) -> str:
    # TODO: use same client as kuberentes.py
    config.load_incluster_config()

    # setup names
    config_map_name = f"wandb-launch-build-context-{run_id}"
    build_job_name = f"wandb-launch-container-build-{run_id}"

    build_context = _upload_build_context(run_id, context_path)
    config_map = _create_dockerfile_configmap(config_map_name, context_path)
    build_job = _create_kaniko_job(build_job_name, config_map.metadata.name, registry, image_uri, build_context)

    batch_v1 = client.BatchV1Api()
    core_v1 = client.CoreV1Api()

    try:
        core_v1.create_namespaced_config_map("wandb", config_map)
        batch_v1.create_namespaced_job("wandb", build_job)

        # wait for double the job deadline since it might take time to schedule
        if not _wait_for_completion(batch_v1, build_job_name, 2 * _DEFAULT_BUILD_TIMEOUT_SECS):
            raise Exception(f"Failed to build image in kaniko for job {run_id}")
    except client.ApiException as e:
        wandb.termerror(f"Exception when creating Kubernetes resources: {e}\n")
    finally:
        wandb.termlog("cleaning up resources")
        try:
            # should we clean up the s3 build contexts? can set bucket level policy to auto deletion
            batch_v1.delete_namespaced_job(build_job_name, "wandb")
            core_v1.delete_namespaced_config_map(config_map_name, "wandb")
        except Exception as e:
            wandb.termerror(f"Exception during Kubernetes resource clean up {e}")

    return image_uri
