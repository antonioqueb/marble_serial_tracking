from odoo import models, fields

class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _get_stock_move_values(
        self, product_id, product_qty, product_uom, location_id,
        name, origin, company_id, values
    ):
        """
        'values' es el diccionario que viene de _prepare_procurement_values() 
        en sale.order.line. Aquí tomamos esos campos y los inyectamos en 
        el diccionario que acabará creando un stock.move.
        """
        # Llamamos primero al método original de Odoo:
        res = super()._get_stock_move_values(
            product_id, product_qty, product_uom, location_id,
            name, origin, company_id, values
        )

        # Si en 'values' viene un 'lot_id' forzado desde la venta,
        # lo guardamos en 'so_lot_id' para luego forzar la reserva en stock_move.py
        forced_lot_id = values.get('lot_id')
        if forced_lot_id:
            res['so_lot_id'] = forced_lot_id

        # Añadimos también tus campos personalizados de mármol
        res.update({
            'marble_height': values.get('marble_height', 0.0),
            'marble_width': values.get('marble_width', 0.0),
            'marble_sqm': values.get('marble_sqm', 0.0),
            'lot_general': values.get('lot_general', ''),
        })
        return res
