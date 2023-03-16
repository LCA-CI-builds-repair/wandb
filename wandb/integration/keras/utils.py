import os
import logging
from typing import Any, List, Union, Optional

import wandb
import tensorflow as tf


logger = logging.getLogger(__name__)

OPTIONAL_ARGS_TYPE = Optional[Union[Union[Any, None], List[Union[Any, None]]]]
MODEL_TYPE = Union[tf.keras.Model, List[tf.keras.Model]]


def load_model_from_artifact(
    artifact_address: str,
    artifact_type: str = "model",
    track_lineage: bool = True,
    model_filepaths: Optional[List[str, os.PathLike]] = None,
    verbose: bool = True,
    custom_objects: OPTIONAL_ARGS_TYPE = None,
    compile: Union[bool, List[bool]] = True,
    options: OPTIONAL_ARGS_TYPE = None,
) -> MODEL_TYPE:
    """A function that automatically loads Keras Models stored as Weights & Biases artifacts.

    Arguments:
        artifact_address (str): address of Weights & Biases artifact storing the Keras model.
        artifact_type (str): type of Weights & Biases artifact storing the Keras model.
        track_lineage (bool): whether to track the lineage of the model artifact usage or not.
            This enables us to track the exact code, hyperparameters, and training dataset used
            to produce the model thus enabling model reproducibility.
        model_filepaths (Optional[List[str, os.PathLike]]): a list of filepaths denoting the
            model files inside the artifact. If your artifact is a single savedmodel, then this
            argument is not necessary, otherwise this argument should be specified.
        verbose (bool): a flag denoting the verbosity of the function. If set to True, the it
            will display messages related to loading the models. This is useful when loading
            multiple models from an artifact.
        custom_objects (Optional[Union[Union[Any, None], List[Union[Any, None]]]]): Optional
            dictionary mapping names (strings) to custom classes or functions to be considered
            during deserialization.
        compile (Union[bool, List[bool]]): whether to compile the model after loading.
        options (Optional[Union[Union[Any, None], List[Union[Any, None]]]]): Optional
            [`tf.saved_model.LoadOptions`](https://www.tensorflow.org/api_docs/python/tf/saved_model/LoadOptions
            object that specifies options for loading from SavedModel.

    Returns:
        (Union[tf.keras.Model, List[tf.keras.Model]]): a Keras model or a list of Keras models.
    """
    if wandb.run is not None:
        model_artifact_dir = (
            wandb.Api().artifact(artifact_address, type=artifact_type).download()
        )
    else:
        if track_lineage:
            model_artifact_dir = wandb.use_artifact(
                artifact_address, type=artifact_type
            ).download()
        else:
            model_artifact_dir = (
                wandb.Api().artifact(artifact_address, type=artifact_type).download()
            )

    if model_filepaths is None:
        wandb.termlog("loading model")
        logger.info("loading model")
        return tf.keras.models.load_model(
            model_artifact_dir,
            custom_objects=custom_objects,
            compile=compile,
            options=options,
        )
    else:
        models = []
        for idx, filepath in enumerate(model_filepaths):
            if verbose:
                wandb.termlog(f"loading model {idx + 1}/{len(model_filepaths)}")
                logger.info(f"loading model {idx + 1}/{len(model_filepaths)}")

            filepath = os.path.join(model_artifact_dir, filepath)

            current_model_custom_objects = (
                custom_objects
                if not isinstance(custom_objects, list)
                else custom_objects[idx]
            )
            current_model_compile = (
                compile if not isinstance(compile, list) else compile[idx]
            )
            current_model_options = (
                options if not isinstance(options, list) else options[idx]
            )

            model = tf.keras.models.load_model(
                model_artifact_dir,
                custom_objects=current_model_custom_objects,
                compile=current_model_compile,
                options=current_model_options,
            )
            models.append(model)

        return models