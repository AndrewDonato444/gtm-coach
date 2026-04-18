# Design Tokens

This project is primarily a backend coaching engine with a thin Streamlit UI. Most styling decisions defer to Streamlit defaults — we don't ship custom CSS unless the friction of using Streamlit's primitives exceeds the cost of styling work.

## Active Tokens

| Token | Value | Notes |
|---|---|---|
| `color-zone-red` | 🔴 emoji | Used in brief output to mark Red Zone (fires) |
| `color-zone-orange` | 🟠 emoji | Used to mark Strategy Zone (leverage plays) |
| `color-zone-green` | 🟢 emoji | Used to mark Mid-Term Reviews (slow burns) |

## Streamlit-managed

- Typography, spacing, layout, button styles → Streamlit defaults
- Dark/light mode → user's Streamlit preference
- Page width / padding → Streamlit's `layout="wide"` setting

## Out of Scope (for now)

- Custom CSS / theme overrides
- Brand colors (no Emburse / Chrome River / Certify visual identity baked in — this is internal coaching tooling, not a customer-facing product)
- Component library (Streamlit primitives are sufficient through Phase 4)

When the product moves off Streamlit (likely Phase 5+ when distribution shifts to Slack / scheduled brief / web), revisit this file with real tokens.
