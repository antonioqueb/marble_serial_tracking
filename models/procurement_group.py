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
    
    def _get_po_line_values_from_proc(self, procurement, partner, company, schedule_date):
        """
        Sobrescribir para evitar reutilizar líneas existentes en productos con tracking
        """
        if hasattr(super(), '_get_po_line_values_from_proc'):
            res = super()._get_po_line_values_from_proc(procurement, partner, company, schedule_date)
        else:
            # Fallback si el método no existe en esta versión
            res = {}
            
        # Para productos con tracking, nunca reutilizar líneas existentes
        if procurement.product_id.tracking != 'none':
            res.pop('purchase_line_id', None)
            _logger.info(f"Eliminando referencia a línea existente para producto con tracking: {procurement.product_id.name}")
            
        return res
    
    def _find_existing_po_line(self, product_id, product_qty, product_uom, location_id, name, origin, company_id, values, po):
        """
        Sobrescribir para que productos con tracking NO reutilicen líneas existentes
        """
        # Si el producto tiene tracking, nunca buscar líneas existentes
        if product_id.tracking != 'none':
            _logger.info(f"Producto {product_id.name} tiene tracking - no se buscará línea existente")
            return False
            
        # Para productos sin tracking, usar el comportamiento normal
        if hasattr(super(), '_find_existing_po_line'):
            return super()._find_existing_po_line(product_id, product_qty, product_uom, location_id, name, origin, company_id, values, po)
        else:
            return False
    
    def _prepare_purchase_order_line(self, product_id, product_qty, product_uom, company_id, values, po):
        """
        Modificar para que no busque líneas existentes para productos con tracking
        """
        res = super()._prepare_purchase_order_line(product_id, product_qty, product_uom, company_id, values, po)
        
        # Si el producto tiene tracking, SIEMPRE forzar creación de nueva línea
        if product_id.tracking != 'none':
            # Eliminar CUALQUIER referencia a línea existente para forzar creación de nueva
            res.pop('purchase_line_id', None)
            
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
            
            _logger.info(f"Forzando nueva línea PO para producto con tracking: {product_id.name} - Campos: altura={values.get('marble_height')}, ancho={values.get('marble_width')}, lote={values.get('lot_general')}")
            
        return res