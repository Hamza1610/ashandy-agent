# Product Category Policy

## Allowed Categories

**Only SKINCARE products are sold via the AI agent.**

This restriction exists because other categories (Makeup, SPMU, Accessories, Discounts, Purchase Points) in the POS system have **outdated prices**.

---

## Categories in POS

| Category | Status | Agent Access |
|----------|--------|--------------|
| **Skincare** | Prices updated | ✅ Can sell |
| Makeup | Outdated prices | ❌ Apologize + alert manager |
| SPMU | Outdated prices | ❌ Apologize + alert manager |
| Accessories | Outdated prices | ❌ Apologize + alert manager |
| Discounts | N/A | ❌ Not applicable |
| Purchase Points | N/A | ❌ Not applicable |

---

## Response Template for Non-Skincare

When a customer asks about non-skincare products, the agent should:

1. **Apologize warmly**
2. **Promise manager follow-up**
3. **Offer skincare alternatives**

### Example Response

> "I'm so sorry love 💕 I currently only assist with our skincare line! But I've noted your interest in [product] - our manager will reach out to you soon about that! While you wait, can I show you our best-selling facial cleansers or moisturizers? ✨"

---

## Instagram Exception

Products synced from Instagram (stored in Pinecone) have **updated prices** for all categories. These can be sold regardless of category.

---

## Manager Alert

The system automatically sends a WhatsApp alert to the manager when:
- Customer inquires about non-skincare PHPPOS items
- Alert includes: customer ID, category, product name
