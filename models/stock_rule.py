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
        Extendemos la salida original para inyectar correctamente
        los datos de mármol manteniendo la asociación con la línea de venta
        """
        # LOGGING mejorado para debug
        _logger.info(f"[STOCK-RULE] Procesando producto: {product_id.name}, origen: {origin}")
        _logger.info(f"[STOCK-RULE] Values recibidos: {values}")
        
        res = super()._get_stock_move_values(
            product_id, product_qty, product_uom, location_id,
            name, origin, company_id, values
        )
        
        # Verificar si hay una línea de venta asociada
        sale_line_id = values.get('sale_line_id')
        if sale_line_id:
            sale_line = self.env['sale.order.line'].browse(sale_line_id)
            if sale_line.exists():
                _logger.info(f"[STOCK-RULE] Línea de venta encontrada: {sale_line.id}")
                
                # Actualizar con los datos actuales de la línea de venta
                marble_data = {
                    'marble_height': sale_line.marble_height,
                    'marble_width': sale_line.marble_width,
                    'marble_sqm': sale_line.marble_sqm,
                    'lot_general': sale_line.lot_general,
                    'pedimento_number': sale_line.pedimento_number,
                    'marble_thickness': sale_line.marble_thickness,
                }
                
                # Lote forzado
                if sale_line.lot_id:
                    marble_data['so_lot_id'] = sale_line.lot_id.id
                    marble_data['lot_id'] = sale_line.lot_id.id
                    
                res.update(marble_data)
                _logger.info(f"[STOCK-RULE] Datos actualizados desde línea de venta: {marble_data}")
        else:
            # Si no hay línea de venta, usar los valores que vienen en el diccionario
            marble_data = {
                'marble_height': values.get('marble_height', 0.0),
                'marble_width': values.get('marble_width', 0.0),
                'marble_sqm': values.get('marble_sqm', 0.0),
                'lot_general': values.get('lot_general', ''),
                'pedimento_number': values.get('pedimento_number', ''),
                'marble_thickness': values.get('marble_thickness', 0.0),
            }
            
            # Lote forzado
            forced_lot = values.get('lot_id')
            if forced_lot:
                marble_data['so_lot_id'] = forced_lot
                marble_data['lot_id'] = forced_lot
                
            res.update(marble_data)
        
        _logger.info(f"[STOCK-RULE] Datos finales enviados al move: {res}")
        
        return res