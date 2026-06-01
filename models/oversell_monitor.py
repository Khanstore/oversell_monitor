from odoo import models, fields, tools


class OversellMonitorLine(models.Model):
    _name = 'oversell.monitor.line'
    _description = 'Oversell / Out-of-Stock Monitor Line'
    _auto = False
    _order = 'order_date desc, vendor_name, product_name'

    order_id = fields.Many2one('sale.order', string='Sale Order', readonly=True)
    order_name = fields.Char(string='Order', readonly=True)
    order_date = fields.Date(string='Order Date', readonly=True)
    order_state = fields.Selection([
        ('draft', 'Quotation'), ('sent', 'Quotation Sent'),
        ('sale', 'Sales Order'), ('done', 'Locked'), ('cancel', 'Cancelled'),
    ], string='Status', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    product_name = fields.Char(string='Product Name', readonly=True)
    default_code = fields.Char(string='SKU', readonly=True)
    ordered_qty = fields.Float(string='Ordered Qty', digits='Product Unit of Measure', readonly=True)
    qty_on_hand = fields.Float(string='Current Stock', digits='Product Unit of Measure', readonly=True)
    deficit_qty = fields.Float(string='Deficit', digits='Product Unit of Measure', readonly=True)
    min_qty_threshold = fields.Float(string='Min Threshold', readonly=True)
    avg_cost = fields.Float(string='Avg Cost', digits='Product Price', readonly=True)
    last_purchase_price = fields.Float(string='Last Purchase Cost', digits='Product Price', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    vendor_id = fields.Many2one('res.partner', string='Vendor', readonly=True)
    vendor_name = fields.Char(string='Vendor', readonly=True)
    vendor_area = fields.Char(string='Area / Region', readonly=True)
    restock_eta = fields.Date(string='Restock ETA', readonly=True)
    open_po_id = fields.Many2one('purchase.order', string='Open PO', readonly=True)
    delivery_status = fields.Char(string='Delivery Status', readonly=True)
    picking_id = fields.Many2one('stock.picking', string='Delivery Order', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    sol.id                              AS id,
                    so.id                               AS order_id,
                    so.name                             AS order_name,
                    so.date_order::date                 AS order_date,
                    so.state                            AS order_state,
                    so.company_id                       AS company_id,
                    COALESCE(sw.id, 1)                  AS warehouse_id,
                    pp.id                               AS product_id,
                    pt.name->>'en_US'                   AS product_name,
                    pt.default_code                     AS default_code,
                    sol.product_uom_qty                 AS ordered_qty,
                    COALESCE(sq.qty_on_hand, 0)         AS qty_on_hand,
                    GREATEST(sol.product_uom_qty - GREATEST(COALESCE(sq.qty_on_hand, 0), 0), 0) AS deficit_qty,
                    COALESCE(orp.product_min_qty, 0)    AS min_qty_threshold,
                    COALESCE((pp.standard_price->>so.company_id::text)::numeric,
                             (pp.standard_price->>'1')::numeric, 0)  AS avg_cost,
                    COALESCE(last_po.price_unit, 0)     AS last_purchase_price,
                    rc.id                               AS currency_id,
                    psi_p.id                            AS vendor_id,
                    COALESCE(psi_p.name, 'Unknown')     AS vendor_name,
                    COALESCE(psi_p.city, psi_p.state_id::text, 'Unknown') AS vendor_area,
                    open_po.date_planned::date          AS restock_eta,
                    open_po.po_id                       AS open_po_id,
                    COALESCE(sp.state, 'none')          AS delivery_status,
                    sp.id                               AS picking_id

                FROM sale_order_line sol
                JOIN sale_order so ON so.id = sol.order_id
                JOIN product_product pp ON pp.id = sol.product_id
                JOIN product_template pt ON pt.id = pp.product_tmpl_id
                JOIN product_category pc ON pc.id = pt.categ_id

                LEFT JOIN (
                    SELECT sq2.product_id, SUM(sq2.quantity) AS qty_on_hand
                    FROM stock_quant sq2
                    JOIN stock_location sl ON sl.id = sq2.location_id AND sl.usage = 'internal'
                    GROUP BY sq2.product_id
                ) sq ON sq.product_id = pp.id

                LEFT JOIN stock_warehouse sw ON sw.company_id = so.company_id

                LEFT JOIN stock_warehouse_orderpoint orp
                    ON orp.product_id = pp.id AND orp.company_id = so.company_id

                LEFT JOIN LATERAL (
                    SELECT pol.price_unit FROM purchase_order_line pol
                    JOIN purchase_order po2 ON po2.id = pol.order_id
                        AND po2.state IN ('purchase', 'done')
                    WHERE pol.product_id = pp.id
                    ORDER BY po2.date_approve DESC NULLS LAST LIMIT 1
                ) last_po ON TRUE

                LEFT JOIN product_supplierinfo psi ON psi.product_tmpl_id = pt.id
                    AND psi.sequence = (
                        SELECT MIN(psi2.sequence) FROM product_supplierinfo psi2
                        WHERE psi2.product_tmpl_id = pt.id)
                LEFT JOIN res_partner psi_p ON psi_p.id = psi.partner_id

                LEFT JOIN res_company rco ON rco.id = so.company_id
                LEFT JOIN res_currency rc ON rc.id = rco.currency_id

                LEFT JOIN LATERAL (
                    SELECT pol2.date_planned, po3.id AS po_id
                    FROM purchase_order_line pol2
                    JOIN purchase_order po3 ON po3.id = pol2.order_id
                        AND po3.state IN ('purchase', 'draft', 'sent')
                    WHERE pol2.product_id = pp.id AND pol2.date_planned IS NOT NULL
                    ORDER BY pol2.date_planned ASC LIMIT 1
                ) open_po ON TRUE

                LEFT JOIN LATERAL (
                    SELECT sp2.id, sp2.state FROM stock_picking sp2
                    WHERE sp2.sale_id = so.id
                      AND EXISTS (
                          SELECT 1 FROM stock_picking_type spt
                          WHERE spt.id = sp2.picking_type_id AND spt.code = 'outgoing')
                    ORDER BY sp2.id DESC LIMIT 1
                ) sp ON TRUE

                WHERE so.state NOT IN ('cancel', 'draft')
                  AND sol.product_id IS NOT NULL
                  AND pt.type != 'service'
                  AND pc.complete_name NOT ILIKE '%%Deliveries%%'
                  AND pc.complete_name NOT ILIKE '%%Delivery%%'
                  AND (
                      COALESCE(sq.qty_on_hand, 0) <= 0
                      OR sol.product_uom_qty > GREATEST(COALESCE(sq.qty_on_hand, 0), 0)
                  )
            )
        """ % self._table)

    def action_create_po(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Create Purchase Order',
            'res_model': 'oversell.create.po.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_line_ids': [(0, 0, {
                    'product_id': rec.product_id.id,
                    'vendor_id': rec.vendor_id.id if rec.vendor_id else False,
                    'deficit_qty': rec.deficit_qty,
                    'last_purchase_price': rec.last_purchase_price,
                }) for rec in self],
            },
        }

    def action_send_vendor_alert(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Send Vendor Alert',
            'res_model': 'oversell.send.alert.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_line_ids': [(0, 0, {
                    'product_id': rec.product_id.id,
                    'vendor_id': rec.vendor_id.id if rec.vendor_id else False,
                    'deficit_qty': rec.deficit_qty,
                    'order_id': rec.order_id.id,
                }) for rec in self],
            },
        }

    def action_view_purchase_history(self):
        """Open all confirmed PO lines for this product."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Purchase History — {self.product_name}',
            'res_model': 'purchase.order.line',
            'view_mode': 'list,form',
            'domain': [
                ('product_id', '=', self.product_id.id),
                ('order_id.state', 'in', ['purchase', 'done']),
            ],
            'context': {'search_default_groupby_partner': 1},
        }
