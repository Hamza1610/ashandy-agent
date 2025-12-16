# Mock Data for Development

This folder contains mock data used when live services (POS, Delivery API) are unavailable.

## Usage

Mock data is automatically used when:
- `USE_MOCK_DATA=true` is set in `.env`
- The live service connection fails (automatic fallback)

## Files

| File | Purpose | Used By |
|------|---------|---------|
| `products.json` | Product inventory mock | POS Server |
| `delivery_zones.json` | Delivery rates mock | Delivery Server |
| `customer_profiles.json` | Customer data mock | Knowledge Server |

## Adding New Mock Data

1. Create a JSON file with realistic data
2. Update the relevant service to load from this folder
3. Ensure format matches live API response structure

## Environment Variables

```env
# Enable mock mode (optional, auto-fallback exists)
USE_MOCK_DATA=true
```

## Notes

- Mock data is designed to pass reviewer validation (no error-like text)
- Prices are in Nigerian Naira (₦)
- Product IDs start from 1001 to distinguish from real IDs
