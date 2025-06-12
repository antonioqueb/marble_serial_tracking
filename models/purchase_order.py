from odoo import models

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def _prepare_stock_moves(self, picking):
        self.ensure_one()
        res = super()._prepare_stock_moves(picking)

        for move_vals in res:
            po_line_id = move_vals.get('purchase_line_id')
            po_line = self.order_line.filtered(lambda l: l.id == po_line_id)

            if po_line:
                altura = po_line.marble_height or 0.0
                ancho = po_line.marble_width or 0.0
                marble_sqm = po_line.marble_sqm

                # Recalcula o ajusta marble_sqm según dimensiones
                if altura > 0 and ancho > 0:
                    marble_sqm = altura * ancho
                elif not marble_sqm:
                    marble_sqm = 0.0

                move_vals.update({
                    'marble_height': altura,
                    'marble_width': ancho,
                    'marble_sqm': marble_sqm,
                    'marble_thickness': po_line.marble_thickness or 0.0,
                    'lot_general': po_line.lot_general or '',
                    'numero_contenedor': po_line.numero_contenedor or '',
                })

        return res
