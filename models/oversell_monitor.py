from odoo import models, fields, api, tools
from datetime import date, timedelta


class OversellMonitorLine(models.Model):
    """
    Transient SQL view that surfaces sale order lines where the ordered
    quantity exceeds available stock at the time the order was confirmed.
    Covers two scenarios:
      1. Product stock was already 0 or negative (out-of-stock, continue-selling ON)
      2. Ordered qty > qty on hand (partial oversell)
    """
    _name = 'oversell.monitor.line'
    _description = 'Oversell / Out-of-Stock Monitor Line'
    _auto = False
    _order = 'order_date desc, vendor_name, product_name'

    # Order info
    order_id = fields.Many2one('sale.order', string='Sale Order', readonly=True)
    order_name = fields.Char(string='Order', readonly=True)
    order_date = fields.Date(string='Order Date', readonly=True)
    order_state = fields.Selection([
        ('draft', 'Quotation'),
        ('sent', 'Quotation Sent'),
        ('sale', 'Sales Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True)

    # Product info
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    product_name = fields.Char(string='Product Name', readonly=True)
    default_code = fields.Char(string='SKU', readonly=True)

    # Qty info
    ordered_qty = fields.Float(string='Ordered Qty', digits='Product Unit of Measure', readonly=True)
    qty_on_hand = fields.Float(string='Current Stock', digits='Product Unit of Measure', readonly=True)
    deficit_qty = fields.Float(string='Deficit', digits='Product Unit of Measure', readonly=True)

    # Cost info
    avg_cost = fields.Float(string='Avg Cost', digits='Product Price', readonly=True)
    last_purchase_price = fields.Float(string='Last Purchase Cost', digits='Product Price', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)

    # Vendor info
    vendor_id = fields.Many2one('res.partner', string='Vendor', readonly=True)
    vendor_name = fields.Char(string='Vendor', readonly=True)
    vendor_area = fields.Char(string='Area / Region', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    sol.id                          AS id,
                    so.id                           AS order_id,
                    so.name                         AS order_name,
                    so.date_order::date             AS order_date,
                    so.state                        AS order_state,

                    pp.id                           AS product_id,
                    pt.name->>'en_US'               AS product_name,
                    pt.default_code                 AS default_code,

                    sol.product_uom_qty             AS ordered_qty,

                    COALESCE(sq.qty_on_hand, 0)     AS qty_on_hand,

                    GREATEST(
                        sol.product_uom_qty - GREATEST(COALESCE(sq.qty_on_hand, 0), 0),
                        0
                    )                               AS deficit_qty,

                    COALESCE((pp.standard_price->>so.company_id::text)::numeric,
                             (pp.standard_price->>'1')::numeric,
                             0)                             AS avg_cost,
                    COALESCE(last_po.price_unit, 0)         AS last_purchase_price,

                    rc.id                           AS currency_id,
                    rp.id                           AS vendor_id,
                    rp.name                         AS vendor_name,
                    COALESCE(rp.city, rp.state_id::text, 'Unknown')  AS vendor_area

                FROM sale_order_line sol
                JOIN sale_order so
                    ON so.id = sol.order_id
                JOIN product_product pp
                    ON pp.id = sol.product_id
                JOIN product_template pt
                    ON pt.id = pp.product_tmpl_id

                -- current stock aggregated per product
                LEFT JOIN (
                    SELECT product_id,
                           SUM(quantity) AS qty_on_hand
                    FROM stock_quant sq2
                    JOIN stock_location sl
                        ON sl.id = sq2.location_id
                       AND sl.usage = 'internal'
                    GROUP BY product_id
                ) sq ON sq.product_id = pp.id

                -- last purchase price from most recent confirmed PO line
                LEFT JOIN LATERAL (
                    SELECT pol.price_unit
                    FROM purchase_order_line pol
                    JOIN purchase_order po2
                        ON po2.id = pol.order_id
                       AND po2.state IN ('purchase','done')
                    WHERE pol.product_id = pp.id
                    ORDER BY po2.date_approve DESC NULLS LAST
                    LIMIT 1
                ) last_po ON TRUE

                -- primary vendor from product supplierinfo
                LEFT JOIN product_supplierinfo psi
                    ON psi.product_tmpl_id = pt.id
                   AND psi.sequence = (
                       SELECT MIN(psi2.sequence)
                       FROM product_supplierinfo psi2
                       WHERE psi2.product_tmpl_id = pt.id
                   )
                LEFT JOIN res_partner rp
                    ON rp.id = COALESCE(psi.partner_id, so.partner_id)

                -- company currency
                LEFT JOIN res_company rco
                    ON rco.id = so.company_id
                LEFT JOIN res_currency rc
                    ON rc.id = rco.currency_id

                WHERE
                    so.state NOT IN ('cancel', 'draft')
                    AND sol.product_id IS NOT NULL
                    AND (
                        -- scenario 1: stock was 0 or negative
                        COALESCE(sq.qty_on_hand, 0) <= 0
                        OR
                        -- scenario 2: ordered more than available
                        sol.product_uom_qty > GREATEST(COALESCE(sq.qty_on_hand, 0), 0)
                    )
            )
        """ % self._table)

    @api.model
    def get_vendor_area(self, vendor_id):
        """Return city or state of vendor partner."""
        partner = self.env['res.partner'].browse(vendor_id)
        return partner.city or (partner.state_id.name if partner.state_id else 'Unknown')
