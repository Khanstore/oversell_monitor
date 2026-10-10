from odoo import models, fields, api, _
from odoo.exceptions import UserError


class CreatePoWizardLine(models.TransientModel):
    _name = 'oversell.create.po.wizard.line'
    _description = 'PO Wizard Line'

    wizard_id = fields.Many2one('oversell.create.po.wizard', string='Wizard')
    product_id = fields.Many2one('product.product', string='Product')
    vendor_id = fields.Many2one('res.partner', string='Vendor')
    deficit_qty = fields.Float(string='Deficit Qty', digits='Product Unit of Measure')
    qty_to_order = fields.Float(string='Qty to Order', digits='Product Unit of Measure')
    last_purchase_price = fields.Float(string='Unit Price', digits='Product Price')


class CreatePoWizard(models.TransientModel):
    _name = 'oversell.create.po.wizard'
    _description = 'Create Purchase Order for Oversell Deficit'

    line_ids = fields.One2many(
        'oversell.create.po.wizard.line', 'wizard_id', string='Products')
    note = fields.Text(string='Notes / Instructions')
    scheduled_date = fields.Date(string='Requested Delivery Date')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'line_ids' not in fields_list:
            return res

        active_ids = self.env.context.get('active_ids', [])
        active_model = self.env.context.get('active_model', '')

        if not active_ids or active_model != 'oversell.monitor.line':
            return res

        # Read directly from the monitor view records
        records = self.env['oversell.monitor.line'].browse(active_ids)
        lines = []
        for rec in records:
            if not rec.product_id:
                continue
            lines.append((0, 0, {
                'product_id': rec.product_id.id,
                'vendor_id': rec.vendor_id.id if rec.vendor_id else False,
                'deficit_qty': rec.deficit_qty,
                'qty_to_order': rec.deficit_qty if rec.deficit_qty > 0 else 0.0,
                'last_purchase_price': rec.last_purchase_price,
            }))

        if lines:
            res['line_ids'] = lines
        return res

    def action_create_po(self):
        valid_lines = self.line_ids.filtered(
            lambda l: l.product_id and l.qty_to_order > 0)
        if not valid_lines:
            raise UserError(_(
                'No valid products to order. '
                'Please ensure each line has a product and quantity greater than zero.'))

        delivery_date = self.scheduled_date or fields.Date.today()

        missing_vendor_lines = valid_lines.filtered(lambda l: not l.vendor_id)
        if missing_vendor_lines:
            products = ', '.join(missing_vendor_lines.mapped('product_id.display_name'))
            raise UserError(_(
                'A vendor is required before creating a purchase order for: %s. '
                'Select a valid supplier on each line.' % products))

        by_vendor = {}
        for line in valid_lines:
            vid = line.vendor_id.id
            by_vendor.setdefault(vid, []).append(line)

        po_ids = []
        for vendor_id, lines in by_vendor.items():
            po = self.env['purchase.order'].create({
                'partner_id': vendor_id,
                'company_id': self.env.company.id,
                'date_planned': delivery_date,
                'order_line': [(0, 0, {
                    'product_id': l.product_id.id,
                    'product_qty': l.qty_to_order,
                    'date_planned': delivery_date,
                }) for l in lines],
            })
            if self.note:
                po.message_post(body=self.note)
            po_ids.append(po.id)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Orders Created'),
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', po_ids)],
        }
