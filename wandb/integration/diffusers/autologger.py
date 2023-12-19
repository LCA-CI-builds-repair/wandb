import logging

from wandb.sdk.integration_utils.auto_logging import AutologAPI

from .pipeline_resolver import DiffusersPipelineResolver

logger = logging.getLogger(__name__)

autolog = AutologAPI(
    name="diffusers",
    symbols=(
        "DiffusionPipeline.__call__",
        "AutoPipelineForText2Image.__call__",
        "AutoPipelineForImage2Image.__call__",
        "AutoPipelineForInpainting.__call__",
        "StableDiffusionPipeline.__call__",
        "KandinskyCombinedPipeline.__call__",
        "KandinskyV22CombinedPipeline.__call__",
        "LatentConsistencyModelPipeline.__call__",
        "LDMTextToImagePipeline.__call__",
        "StableDiffusionPanoramaPipeline.__call__",
        "StableDiffusionParadigmsPipeline.__call__",
        "PixArtAlphaPipeline.__call__",
        "StableDiffusionSAGPipeline.__call__",
        "SemanticStableDiffusionPipeline.__call__",
        "WuerstchenCombinedPipeline.__call__",
        "AltDiffusionPipeline.__call__",
        "StableDiffusionAttendAndExcitePipeline.__call__",
        "StableDiffusionXLPipeline.__call__",
        "StableDiffusionXLImg2ImgPipeline.__call__",
        "IFPipeline.__call__",
        "BlipDiffusionPipeline.__call__",
        "BlipDiffusionControlNetPipeline.__call__",
        "StableDiffusionControlNetPipeline.__call__",
        "StableDiffusionControlNetImg2ImgPipeline.__call__",
        "StableDiffusionControlNetInpaintPipeline.__call__",
        "CycleDiffusionPipeline.__call__",
        "StableDiffusionInstructPix2PixPipeline.__call__",
        "PaintByExamplePipeline.__call__",
        "RePaintPipeline.__call__",
        "KandinskyImg2ImgCombinedPipeline.__call__",
        "KandinskyInpaintCombinedPipeline.__call__",
        "KandinskyV22Img2ImgCombinedPipeline.__call__",
        "KandinskyV22InpaintCombinedPipeline.__call__",
        "AnimateDiffPipeline.__call__",
        "AudioLDMPipeline.__call__",
        "AudioLDM2Pipeline.__call__",
        "MusicLDMPipeline.__call__",
        "StableDiffusionPix2PixZeroPipeline.__call__",
        "PNDMPipeline.__call__",
        "ShapEPipeline.__call__",
        "StableDiffusionImg2ImgPipeline.__call__",
        "StableDiffusionInpaintPipeline.__call__",
        "StableDiffusionDepth2ImgPipeline.__call__",
        "StableDiffusionImageVariationPipeline.__call__",
        "StableDiffusionPipelineSafe.__call__",
        "StableDiffusionUpscalePipeline.__call__",
        "StableDiffusionAdapterPipeline.__call__",
        "StableDiffusionGLIGENPipeline.__call__",
        "StableDiffusionModelEditingPipeline.__call__",
        "VersatileDiffusionTextToImagePipeline.__call__",
        "VersatileDiffusionImageVariationPipeline.__call__",
        "VersatileDiffusionDualGuidedPipeline.__call__",
        "LDMPipeline.__call__",
        "TextToVideoSDPipeline.__call__",
        "TextToVideoZeroPipeline.__call__",
        "StableVideoDiffusionPipeline.__call__",
    ),
    resolver=DiffusersPipelineResolver(),
    telemetry_feature="diffusers_autolog",
)
