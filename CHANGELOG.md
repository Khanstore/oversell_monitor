## 18.0.2.1.3 — 2026-10-12
- Fix: remove unsupported `formatLang` calls from the QWeb PDF report, which caused `TypeError: 'NoneType' object is not callable` during rendering.
- Format shortage quantities with a safe numeric format and use Odoo's monetary field widget for average and last-purchase prices.
- Validation: XML syntax and ZIP integrity checked; live Odoo PDF rendering still requires staging verification.

## 18.0.2.1.2 — 2026-10-11
- Updated the existing QWeb PDF report to match the requested vendor/shortage print layout.
- Set A4 landscape with narrow 12.7 mm margins.
- Added Place, Vendor and Mobile Number, Product Variant, Shortage, Avg Price, Last Purchase and Comment columns.
- Comment includes order reference/status and restock ETA when available.
- Kept the report bound to the Oversell Monitor model so it is available from the list Print menu.

# Changelog

## 18.0.2.1.1 — 2026-10-10

- Fix: include `sent` (Quotation Sent) sale orders in the live oversell / out-of-stock report.
- Confirmed sales orders and locked orders are allocated available stock before sent quotations, so an unconfirmed quote does not displace confirmed demand in the report's allocation priority.
- This affects the live report only. Historical confirmation-time snapshots remain tied to order confirmation; sent quotations do not create permanent oversell-history events until confirmed.
- Validation: source-level patch; Odoo runtime installation and database tests have not been run in this environment.

## 18.0.2.1.0 — 2026-10-10

- Reworked the live report to scope stock to the sales order warehouse and company.
- Use free quantity (`quantity - reserved_quantity`) rather than physical quantity alone.
- Convert open sales demand to the product UoM and allocate stock oldest-order-first to reduce double-counting across orders.
- Use outstanding quantity (ordered minus delivered) in the live report.
- Apply the highest of product, reorder-point and global minimum thresholds.
- Capture order-confirmation shortage snapshots in the history model.
- Make the digest enabled/frequency settings control the scheduled action.
- Escape dynamic text in generated email HTML and queue automatic alerts instead of sending synchronously.
- Prevent purchase-order creation without a valid supplier; do not default a zero shortage to the full sales quantity.
- Set history relations to `set null` so history values can survive record deletion.

## Important validation notes

This is a source-level improvement release. It has not been installed or executed against a live Odoo 18 server in this environment. Test the SQL view on a staging database before production deployment. In particular, confirm customizations to stock warehouse/location structures, multi-company rules, units of measure, vendor price currency, and email templates. The historical snapshot captures available/free quantity immediately before confirmation; it is not a reconstruction of stock at an earlier quotation date.
