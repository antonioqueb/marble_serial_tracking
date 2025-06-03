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
        result = {}
        
        for procurement in procurements:
            product_id = procurement.product_id
            
            # Si el producto tiene tracking (mármol), no permitir agrupamiento
            # Crear un grupo único para cada procurement
            if product_id.tracking != 'none':
                # Crear una clave única para cada procurement para evitar agrupamiento
                unique_key = (
                    procurement.product_id.id,
                    procurement.location_id.id,
                    procurement.company_id.id,
                    procurement.values.get('sale_line_id', 0),  # Incluir sale_line_id para unicidad
                    id(procurement)  # ID único del objeto procurement
                )
                result[unique_key] = [procurement]
                _logger.info(f"[PROCUREMENT-MERGE] Producto con tracking {product_id.name}: creando grupo único")
            else:
                # Para productos sin tracking, usar el comportamiento normal de agrupamiento
                # Usar la implementación padre para estos procurements
                normal_result = super()._get_procurements_to_merge([procurement])
                result.update(normal_result)
                _logger.info(f"[PROCUREMENT-MERGE] Producto sin tracking {product_id.name}: agrupamiento normal")
        
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