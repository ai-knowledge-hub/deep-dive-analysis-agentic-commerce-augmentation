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
metadata (confidence, merchant, offer URL) is preserved so empowerment scoring
and agents can reason about data quality.
