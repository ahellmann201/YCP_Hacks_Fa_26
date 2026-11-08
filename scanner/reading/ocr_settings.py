"""Bounded OCR parallelism for the Pi's shared model sessions."""
import os


def ocr_threads():
    value = os.environ.get('SCANNER_OCR_THREADS', '1')
    if value not in {'1', '2', '3', '4'}:
        raise ValueError('SCANNER_OCR_THREADS must be 1, 2, 3 or 4')
    return int(value)


def rapidocr_parameters(threads=None):
    from rapidocr import ModelType, OCRVersion
    return {
        'Det.ocr_version':OCRVersion.PPOCRV5, 'Det.model_type':ModelType.MOBILE,
        'Rec.ocr_version':OCRVersion.PPOCRV5, 'Rec.model_type':ModelType.MOBILE,
        'Det.limit_side_len':640, 'Det.limit_type':'max',
        'Rec.rec_batch_num':1, 'Cls.cls_batch_num':1,
        'EngineConfig.onnxruntime.intra_op_num_threads':ocr_threads() if threads is None else threads,
        'EngineConfig.onnxruntime.inter_op_num_threads':1,
        'EngineConfig.onnxruntime.enable_cpu_mem_arena':False,
    }
