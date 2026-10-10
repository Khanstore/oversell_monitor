from odoo import models, fields, api


class OversellHistory(models.Model):
    """Permanent log of oversell events — survives stock replenishment."""
    _name = 'oversell.history'
    _description = 'Oversell History Log'
    _order = 'event_date desc'
    _rec_name = 'order_id'

    event_date = fields.Datetime(string='Event Date', default=fields.Datetime.now, readonly=True)
    order_id = fields.Many2one('sale.order', string='Sale Order', readonly=True, ondelete='set null')
    order_name = fields.Char(string='Order Ref', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True, ondelete='set null')
    vendor_id = fields.Many2one('res.partner', string='Vendor', readonly=True)
    vendor_area = fields.Char(string='Area', readonly=True)
    ordered_qty = fields.Float(string='Ordered Qty', digits='Product Unit of Measure', readonly=True)
    stock_at_order = fields.Float(string='Stock at Order Time', digits='Product Unit of Measure', readonly=True)
    deficit_qty = fields.Float(string='Deficit Qty', digits='Product Unit of Measure', readonly=True)
    avg_cost = fields.Float(string='Avg Cost', digits='Product Price', readonly=True)
    last_purchase_price = fields.Float(string='Last Purchase Price', digits='Product Price', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    po_created = fields.Boolean(string='PO Created', default=False)
    po_id = fields.Many2one('purchase.order', string='Purchase Order')
    alert_sent = fields.Boolean(string='Alert Sent', default=False)
    company_id = fields.Many2one('res.company', string='Company',
                                  default=lambda self: self.env.company)
    notes = fields.Text(string='Notes')

    @api.model
    def log_oversell(self, sale_order_line, stock_qty, deficit, avg_cost, last_cost, vendor, area, currency):
        """Called by automation rule when a qualifying order line is detected."""
        existing = self.search([
            ('order_id', '=', sale_order_line.order_id.id),
            ('product_id', '=', sale_order_line.product_id.id),
        ], limit=1)
        if existing:
            return existing
        return self.create({
            'order_id': sale_order_line.order_id.id,
            'order_name': sale_order_line.order_id.name,
            'product_id': sale_order_line.product_id.id,
            'vendor_id': vendor,
            'vendor_area': area,
            'ordered_qty': sale_order_line.product_uom_qty,
            'stock_at_order': stock_qty,
            'deficit_qty': deficit,
            'avg_cost': avg_cost,
            'last_purchase_price': last_cost,
            'currency_id': currency,
            'company_id': sale_order_line.order_id.company_id.id,
        })
