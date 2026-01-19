# Feed Schema

All adapters must emit `RawOffer` objects:

```python
@dataclass
class RawOffer:
    source: str
    source_id: str
    merchant_name: Optional[str]
    offer_url: Optional[str]
    title: str
    description: Optional[str]
    price: float
    currency: str
    availability: str
    inventory_quantity: Optional[int]
    variant_attributes: Dict[str, Any]
    media: List[str]
    attributes: Dict[str, Any]
    confidence: float
    completeness: float
    inferred_fields: List[str]
```

These are converted into `RawProduct` and then canonical `Product` models. All
metadata (confidence, merchant, offer URL) is preserved so alignment scoring
and the intentionality profiler can reason about data quality.

## Intentionality Enrichment

After conversion to `Product`, products can be enriched with an `IntentionalityProfile`:

```python
@dataclass
class IntentionalityProfile:
    product_id: str
    capabilities_enabled: List[str]    # What human capabilities this enables
    goals_served: List[str]            # What goals this helps achieve
    prerequisites: List[str]           # What user needs to benefit
    outcomes_expected: List[str]       # What changes after purchase
    context_fit: Dict[str, float]      # Fit scores for different contexts
```

This transformation makes products legible to LLM intent inference.
