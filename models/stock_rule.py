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
        _logger.info(f"[STOCK-RULE] === INICIO _get_stock_move_values ===")
        _logger.info(f"[STOCK-RULE] Producto: {product_id.name}, Origen: {origin}")
        _logger.info(f"[STOCK-RULE] Values recibidos: {values}")
        
        res = super()._get_stock_move_values(
            product_id, product_qty, product_uom, location_id,
            name, origin, company_id, values
        )
        
        sale_line_id = values.get('sale_line_id')
        _logger.info(f"[STOCK-RULE] sale_line_id en values: {sale_line_id}")
        
        if sale_line_id:
            sale_line = self.env['sale.order.line'].browse(sale_line_id)
            if sale_line.exists():
                _logger.info(f"[STOCK-RULE] Línea de venta encontrada: {sale_line.id}")
                _logger.info(f"[STOCK-RULE] Datos de la línea de venta:")
                _logger.info(f"  - Lote: {sale_line.lot_id.name if sale_line.lot_id else 'Sin lote'}")
                _logger.info(f"  - Dimensiones: {sale_line.marble_height}x{sale_line.marble_width} = {sale_line.marble_sqm}m²")
                _logger.info(f"  - Lote General: {sale_line.lot_general}")
                _logger.info(f"  - Pedimento: {sale_line.pedimento_number}")
                
                marble_data = {
                    'marble_height': sale_line.marble_height,
                    'marble_width': sale_line.marble_width,
                    'marble_sqm': sale_line.marble_sqm,
                    'lot_general': sale_line.lot_general,
                    'pedimento_number': sale_line.pedimento_number,
                    'marble_thickness': sale_line.marble_thickness,
                }
                
                if sale_line.lot_id:
                    marble_data.update({
                        'so_lot_id': sale_line.lot_id.id,
                        'lot_id': sale_line.lot_id.id,
                    })
                    _logger.info(f"[STOCK-RULE] Asignando lot_id: {sale_line.lot_id.id}")
                
                res.update(marble_data)
                _logger.info(f"[STOCK-RULE] Datos actualizados desde línea de venta")
            else:
                _logger.warning(f"[STOCK-RULE] Línea de venta {sale_line_id} no existe!")
        else:
            _logger.info(f"[STOCK-RULE] No hay sale_line_id, usando valores del diccionario")
            marble_data = {
                'marble_height':    values.get('marble_height', 0.0),
                'marble_width':     values.get('marble_width', 0.0),
                'marble_sqm':       values.get('marble_sqm', 0.0),
                'lot_general':      values.get('lot_general', ''),
                'pedimento_number': values.get('pedimento_number', ''),
                'marble_thickness': values.get('marble_thickness', 0.0),
            }
            
            forced_lot = values.get('lot_id')
            if forced_lot:
                marble_data.update({
                    'so_lot_id': forced_lot,
                    'lot_id': forced_lot,
                })
                _logger.info(f"[STOCK-RULE] Usando lot_id forzado: {forced_lot}")
                
            res.update(marble_data)
        
        _logger.info(f"[STOCK-RULE] Valores finales para stock.move:")
        _logger.info(f"  - marble_height: {res.get('marble_height')}")
        _logger.info(f"  - marble_width: {res.get('marble_width')}")
        _logger.info(f"  - marble_sqm: {res.get('marble_sqm')}")
        _logger.info(f"  - lot_general: {res.get('lot_general')}")
        _logger.info(f"  - pedimento_number: {res.get('pedimento_number')}")
        _logger.info(f"  - lot_id: {res.get('lot_id')}")
        _logger.info(f"[STOCK-RULE] === FIN _get_stock_move_values ===")
        
        return res