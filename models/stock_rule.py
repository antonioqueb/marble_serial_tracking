from odoo import models, fields

class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _get_stock_move_values(
        self, product_id, product_qty, product_uom, location_id,
        name, origin, company_id, values
    ):
        """
        values es el diccionario que viene de _prepare_procurement_values() 
        en sale.order.line. Aquí tomamos esos campos y los inyectamos en 
        el diccionario que acabará creando un stock.move.
        """
        # Llamamos al super con la firma correcta:
        res = super()._get_stock_move_values(
            product_id, product_qty, product_uom, location_id,
            name, origin, company_id, values
        )
        # Copiamos tus campos personalizados. Ajusta según tu lógica:
        res.update({
            'marble_height': values.get('marble_height', 0.0),
            'marble_width': values.get('marble_width', 0.0),
            'marble_sqm': values.get('marble_sqm', 0.0),
            'lot_general': values.get('lot_general', '')
        })
        return res
