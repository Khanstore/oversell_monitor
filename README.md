# Oversell & Out-of-Stock Monitor — Odoo 18

## Release

Version: `18.0.2.1.2`

## Main improvements in this release

- Includes `Quotation Sent` (`sale.order.state = sent`) orders in the live out-of-stock / oversell report. Confirmed orders are given allocation priority over sent quotations. Sent quotations are potential demand, not confirmed commitments, and do not create history snapshots until confirmation.

- Live report stock is scoped to the sales order warehouse and company.
- Free stock subtracts reserved quantities.
- Outstanding demand is ordered minus delivered quantity and converted to the product's default unit of measure.
- Demand is allocated oldest-order-first within each company / warehouse / product group to reduce the same stock being counted repeatedly against different orders.
- Product, reorder-point and global minimum thresholds are considered in the live report.
- Sales order confirmation can create a persistent history snapshot when order demand exceeds free stock.
- Digest schedule settings update the associated scheduled action.
- Optional automatic email alerts are queued rather than sent synchronously during confirmation.
- Purchase-order creation now requires a vendor and only uses a positive deficit quantity.

## Installation / upgrade

1. Back up the database and filestore.
2. Test on a copy of the target Odoo 18 database first.
3. Extract this folder into a directory on the Odoo addons path.
4. Restart Odoo and update the Apps list.
5. Install the module on a fresh database, or upgrade the existing module from Apps / command line.
6. Open **Oversell Monitor → Settings** and save the digest/notification settings you intend to use.
7. Configure and test outgoing mail before enabling automated notifications.

## Important semantics

- The live report is a *current fulfillment-risk view*, not a historical reconstruction. `Outstanding Qty` is ordered minus delivered quantity. `Free Stock` is stock quantity minus reservations within the order's warehouse.
- The history snapshot is captured immediately before sales-order confirmation. It is not a promise that stock was available at quotation creation time.
- Minimum-stock thresholds can show a row with zero sales shortage. Such a row must not generate a purchase order unless a positive quantity is entered.
- Automatic vendor/customer notifications are disabled unless their respective settings are enabled. Emails are queued in Odoo's mail system.

## Staging validation checklist

- Fresh install and upgrade from the previous release.
- Two orders for the same product competing for limited stock.
- Reservations, partial deliveries, cancellations, and backorders.
- Two warehouses in one company and two companies with separate stock.
- Sales and product units of measure that differ.
- Product, reorder-point and global thresholds, including zero threshold.
- Confirmation-time history is created once per order/product and not duplicated on retries.
- Vendor/customer email settings, mail queue, missing addresses and failed delivery.
- Vendor-specific purchase pricing, currencies, minimum quantities and company-specific suppliers.
- Large-volume query performance and database execution plan.

## Known limitations / items for next iteration

- The live report uses the English (`en_US`) product translation for its SQL display label. The UI should ideally resolve the active-language name at presentation time.
- Purchase-order pricing still needs a dedicated vendor-currency and supplier-rule audit before unattended purchasing. Review every generated PO before confirmation.
- History is a confirmation-time shortage snapshot; stock reservation races and concurrent order confirmations need transaction-level integration tests.
- Dashboard aggregates should be reviewed because a live report can contain one row per affected sales line.
- This release has been syntax-checked locally but has not been run inside Odoo. Treat it as a staging candidate, not a production-certified build.


## Printable vendor report

Version `18.0.2.1.2` updates the existing QWeb PDF report to match the requested printed layout: A4 landscape, narrow margins (12.7 mm), centered title/date, clear table borders, and columns for Place, Vendor and Mobile Number, Product Variant, Shortage, Avg Price, Last Purchase, and Comment. The Comment column includes the source order/status and restock ETA when available. From the Oversell Monitor list, select records if desired and use **Print → Stock Shortage & Vendor Report**. The report is based on selected report records when selection is used; it does not create a separate static spreadsheet.


### v18.0.2.1.3 report hotfix (2026-10-12)

Fixed QWeb PDF rendering by removing `formatLang` calls from the printable shortage report. Monetary values use Odoo's monetary widget; shortage quantities use numeric formatting. Please upgrade on a staging database and verify PDF rendering before production deployment.
