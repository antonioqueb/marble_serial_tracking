# models/procurement_group.py
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class StockRule(models.Model):
    _inherit = 'stock.rule'
    
    def _get_procurements_to_merge(self, procurements):
        """
        Filtrar los procurements que pueden ser agrupados.
        Para productos con tracking (mármol), devolver lista vacía para evitar agrupamiento.
        """
        procurement_groups = {}
        
        for procurement in procurements:
            # Si el producto tiene tracking, no permitir agrupamiento
            if procurement.product_id.tracking != 'none':
                _logger.info(f"Producto {procurement.product_id.name} tiene tracking - no se agrupará")
                continue
                
            # Para otros productos, mantener comportamiento normal
            key = self._get_procurement_group_key(procurement)
            if key not in procurement_groups:
                procurement_groups[key] = []
            procurement_groups[key].append(procurement)
        
        # Devolver solo los grupos de procurements que pueden ser fusionados
        result = []
        for group in procurement_groups.values():
            if len(group) > 1:
                result.extend(group)
        
        return result
    
    def _get_procurement_group_key(self, procurement):
        """
        Crear una clave única para agrupar procurements
        """
        return (
            procurement.product_id.id,
            procurement.location_id.id,
            procurement.company_id.id,
            procurement.values.get('supplier_id'),
            procurement.values.get('group_id'),
        )
    
    def _prepare_purchase_order_line(self, product_id, product_qty, product_uom, company_id, values, po):
        """
        Modificar para que no busque líneas existentes para productos con tracking
        """
        res = super()._prepare_purchase_order_line(product_id, product_qty, product_uom, company_id, values, po)
        
        # Si el producto tiene tracking, forzar creación de nueva línea
        if product_id.tracking != 'none':
            # Buscar si ya existe una línea para evitar duplicados cuando no es necesario
            existing_line = po.order_line.filtered(
                lambda line: line.product_id == product_id 
                and line.product_uom == product_uom
                and not line.marble_height  # Solo si no tiene datos de mármol
            )
            
            if not existing_line:
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