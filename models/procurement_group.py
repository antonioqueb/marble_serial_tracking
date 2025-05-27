# models/procurement_group.py
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class StockRule(models.Model):
    _inherit = 'stock.rule'
    
    def _get_procurements_to_merge(self, procurements):
        """
        Sobrescribir para evitar que se agrupen las líneas de productos con tracking
        """
        # Separar procurements por tipo de tracking
        trackable_procurements = []
        normal_procurements = []
        
        for procurement in procurements:
            if procurement.product_id.tracking != 'none':
                trackable_procurements.append(procurement)
                _logger.info(f"Producto {procurement.product_id.name} tiene tracking - se procesará individualmente")
            else:
                normal_procurements.append(procurement)
        
        # Procesar productos con tracking individualmente (sin agrupamiento)
        merged_procurements = []
        for procurement in trackable_procurements:
            # Cada procurement con tracking se mantiene separado
            merged_procurements.append([procurement])
        
        # Para productos sin tracking, usar el comportamiento normal de agrupamiento
        if normal_procurements:
            normal_merged = super()._get_procurements_to_merge(normal_procurements)
            merged_procurements.extend(normal_merged)
            
        return merged_procurements
    
    def _prepare_purchase_order_line(self, product_id, product_qty, product_uom, company_id, values, po):
        """
        Modificar para que no busque líneas existentes para productos con tracking
        """
        res = super()._prepare_purchase_order_line(product_id, product_qty, product_uom, company_id, values, po)
        
        # Si el producto tiene tracking, forzar creación de nueva línea
        if product_id.tracking != 'none':
            # Eliminar el ID de línea existente para forzar creación de nueva
            if 'purchase_line_id' in res:
                del res['purchase_line_id']
                
            # Asegurar que los campos de mármol se propaguen
            res.update({
                'order_id': po.id,
                'marble_height': values.get('marble_height', 0.0),
                'marble_width': values.get('marble_width', 0.0),
                'marble_sqm': values.get('marble_sqm', 0.0),
                'lot_general': values.get('lot_general', ''),
                'bundle_code': values.get('bundle_code', ''),
                'marble_thickness': values.get('marble_thickness', 0.0),
            })
            
            _logger.info(f"Creando nueva línea PO para producto con tracking: {product_id.name}")
            
        return res