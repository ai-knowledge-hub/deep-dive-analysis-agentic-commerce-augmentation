"""Evidence-first modules for open-world product representations."""

from modules.evidence.domain import EvidenceProduct
from modules.evidence.retriever import retrieve
from modules.evidence.normalizer import to_product
from modules.evidence.optimizer import optimize
from modules.evidence.verify import simulate_actual, average_alignment

__all__ = [
    "EvidenceProduct",
    "retrieve",
    "to_product",
    "optimize",
    "simulate_actual",
    "average_alignment",
]
