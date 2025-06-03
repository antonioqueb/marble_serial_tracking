# models/procurement_group.py
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class StockRule(models.Model):
    _inherit = 'stock.rule'
    
    def _get_procurements_to_merge(self, procurements):
        """
        Sobrescribir para evitar que se agrupen las líneas de productos con tracking
        En Odoo 18, este método recibe una lista de procurements, no parámetros individuales
        """
        # Separar procurements por tipo de producto
        tracking_procurements = []
        normal_procurements = []
        
        for procurement in procurements:
            if procurement.product_id.tracking != 'none':
                tracking_procurements.append(procurement)
                _logger.info(f"[PROCUREMENT-MERGE] Producto con tracking {procurement.product_id.name}: sin agrupamiento")
            else:
                normal_procurements.append(procurement)
                _logger.info(f"[PROCUREMENT-MERGE] Producto sin tracking {procurement.product_id.name}: agrupamiento normal")
        
        # Inicializar resultado
        result = {}
        
        # Para productos con tracking: cada procurement en su propio grupo (sin agrupar)
        for i, procurement in enumerate(tracking_procurements):
            # Crear una clave hashable única para cada procurement
            # Usar el ID del procurement más un contador para asegurar unicidad
            unique_key = (
                'tracking_product',
                procurement.product_id.id,
                procurement.location_id.id,
                procurement.company_id.id,
                procurement.values.get('sale_line_id', 0),
                i  # Contador para garantizar unicidad
            )
            result[unique_key] = [procurement]
        
        # Para productos sin tracking: usar el agrupamiento normal
        if normal_procurements:
            normal_result = super()._get_procurements_to_merge(normal_procurements)
            result.update(normal_result)
        
        _logger.info(f"[PROCUREMENT-MERGE] Total grupos creados: {len(result)}")
        return result
    
    def _prepare_purchase_order_line(self, product_id, product_qty, product_uom, company_id, values, po):
        """
        Modificar para que no busque líneas existentes para productos con tracking
        Y PROPAGAR CORRECTAMENTE todos los campos de mármol
        """
        res = super()._prepare_purchase_order_line(product_id, product_qty, product_uom, company_id, values, po)
        
        # Logging para debug
        _logger.info(f"[PROCUREMENT-DEBUG] Values recibidos: {values}")
        _logger.info(f"[PROCUREMENT-DEBUG] Producto: {product_id.name}, Tracking: {product_id.tracking}")
        
        # Si el producto tiene tracking, forzar creación de nueva línea
        if product_id.tracking != 'none':
            # Eliminar el ID de línea existente para forzar creación de nueva
            if 'purchase_line_id' in res:
                del res['purchase_line_id']
                
            # ASEGURAR que los campos de mármol se propaguen SIEMPRE
            marble_fields = {
                'order_id': po.id,
                'marble_height': values.get('marble_height', 0.0),
                'marble_width': values.get('marble_width', 0.0),
                'marble_sqm': values.get('marble_sqm', 0.0),
                'lot_general': values.get('lot_general', ''),
                'bundle_code': values.get('bundle_code', ''),
                'marble_thickness': values.get('marble_thickness', 0.0),
            }
            
            res.update(marble_fields)
            
            _logger.info(f"[PROCUREMENT-DEBUG] Campos de mármol propagados: {marble_fields}")
            _logger.info(f"Creando nueva línea PO para producto con tracking: {product_id.name}")
        else:
            # Para productos sin tracking, también propagar si existen los valores
            marble_fields = {}
            for field in ['marble_height', 'marble_width', 'marble_sqm', 'lot_general', 'marble_thickness']:
                if field in values:
                    marble_fields[field] = values[field]
            
            if marble_fields:
                res.update(marble_fields)
                _logger.info(f"[PROCUREMENT-DEBUG] Campos de mármol propagados (sin tracking): {marble_fields}")
            
        return res