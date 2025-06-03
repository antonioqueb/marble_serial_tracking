# models/stock_rule.py
from odoo import models
import logging

_logger = logging.getLogger(__name__)

class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _get_stock_move_values(
        self, product_id, product_qty, product_uom, location_id,
        name, origin, company_id, values
    ):
        """
        *Extendemos* la salida original para inyectar:
        • Lote forzado (solo si existe)
        • Datos de mármol
        • Número de pedimento
        """
        # LOGGING para debug - ver qué llega al stock rule
        _logger.info(f"[STOCK-RULE-DEBUG] Producto: {product_id.name}")
        _logger.info(f"[STOCK-RULE-DEBUG] Values recibidos: {values}")
        
        res = super()._get_stock_move_values(
            product_id, product_qty, product_uom, location_id,
            name, origin, company_id, values
        )

        # Lote forzado (solo si viene desde la venta Y existe)
        forced_lot = values.get('lot_id')
        if forced_lot:
            res['so_lot_id'] = forced_lot
            res['lot_id']    = forced_lot

        # Datos adicionales incluyendo pedimento_number
        marble_data = {
            'marble_height':    values.get('marble_height', 0.0),
            'marble_width':     values.get('marble_width',  0.0),
            'marble_sqm':       values.get('marble_sqm',    0.0),
            'lot_general':      values.get('lot_general',   ''),
            'pedimento_number': values.get('pedimento_number', ''),
            'marble_thickness': values.get('marble_thickness', 0.0),
        }
        
        res.update(marble_data)
        
        # LOGGING para ver qué se está enviando al stock move
        _logger.info(f"[STOCK-RULE-DEBUG] Datos de mármol enviados al move: {marble_data}")
        
        return res