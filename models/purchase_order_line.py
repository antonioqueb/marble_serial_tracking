from odoo import models, fields, api

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    marble_height = fields.Float('Altura (m)', store=True)
    marble_width = fields.Float('Ancho (m)', store=True)
    marble_sqm = fields.Float('m²', compute='_compute_marble_sqm', store=True, readonly=False)
    lot_general = fields.Char('Lote', store=True)
    marble_thickness = fields.Float('Grosor (cm)')

    @api.depends('marble_height', 'marble_width')
    def _compute_marble_sqm(self):
        """
        Lógica de cálculo HÍBRIDA:
        - Si se especifican altura y ancho, calcula los m².
        - Si NO se especifican, NO HACE NADA, permitiendo que el valor
          introducido manualmente por el usuario se conserve.
        """
        for line in self:
            if line.marble_height > 0 and line.marble_width > 0:
                line.marble_sqm = line.marble_height * line.marble_width

    # El resto de los métodos se mantienen igual, son correctos.
    @api.onchange('marble_height', 'marble_width', 'lot_general')
    def _onchange_marble_fields(self):
        # Aquí puedes añadir lógica adicional si es necesario
        return

    def write(self, vals):
        res = super().write(vals)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        return lines

    def _prepare_stock_move_vals(self, picking, price_unit, product_uom_qty, product_uom):
        self.ensure_one()
        vals = super()._prepare_stock_move_vals(picking, price_unit, product_uom_qty, product_uom)
        vals.update({
            'marble_height': self.marble_height or 0.0,
            'marble_width': self.marble_width or 0.0,
            'marble_sqm': self.marble_sqm or 0.0,
            'lot_general': self.lot_general or '',
            'marble_thickness': self.marble_thickness or 0.0,
        })
        return vals

    def _create_stock_moves(self, picking):
        res = self.env['stock.move']
        for line in self:
            moves = super(PurchaseOrderLine, line)._create_stock_moves(picking)
            res |= moves
        return res