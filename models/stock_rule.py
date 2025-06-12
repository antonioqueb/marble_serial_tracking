# models/stock_rule.py

from odoo import models

class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _get_stock_move_values(
        self, product_id, product_qty, product_uom, location_id,
        name, origin, company_id, values
    ):
        res = super()._get_stock_move_values(
            product_id, product_qty, product_uom,
            location_id, name, origin, company_id, values
        )

        sale_line_id = values.get('sale_line_id')
        if sale_line_id:
            sale_line = self.env['sale.order.line'].browse(sale_line_id)
            if sale_line.exists():
                marble_data = {
                    'marble_height':    sale_line.marble_height,
                    'marble_width':     sale_line.marble_width,
                    'marble_sqm':       sale_line.marble_sqm,
                    'lot_general':      sale_line.lot_general,
                    'pedimento_number': sale_line.pedimento_number,
                    'marble_thickness': sale_line.marble_thickness,
                    'numero_contenedor': sale_line.numero_contenedor,
                }
                if sale_line.lot_id:
                    marble_data.update({
                        'so_lot_id': sale_line.lot_id.id,
                        'lot_id':    sale_line.lot_id.id,
                    })
                res.update(marble_data)
        else:
            marble_data = {
                'marble_height':    values.get('marble_height', 0.0),
                'marble_width':     values.get('marble_width', 0.0),
                'marble_sqm':       values.get('marble_sqm', 0.0),
                'lot_general':      values.get('lot_general', ''),
                'pedimento_number': values.get('pedimento_number', ''),
                'marble_thickness': values.get('marble_thickness', 0.0),
                'numero_contenedor': values.get('numero_contenedor', ''),
            }
            forced_lot = values.get('lot_id')
            if forced_lot:
                marble_data.update({
                    'so_lot_id': forced_lot,
                    'lot_id':    forced_lot,
                })
            res.update(marble_data)

        return res
