# models/procurement_group.py
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class StockRule(models.Model):
    _inherit = 'stock.rule'
    
    def _get_procurements_to_merge(self, procurements):
        """
        Para productos con tracking: NO AGRUPAR NUNCA
        Cada procurement debe generar su propia línea de PO
        """
        merged_procurements = []
        
        for procurement in procurements:
            if procurement.product_id.tracking != 'none':
                # Cada producto con tracking va en su propio grupo (no se agrupa)
                merged_procurements.append([procurement])
                _logger.info(f"Producto {procurement.product_id.name} con tracking - procesamiento individual")
            else:
                # Para productos sin tracking, mantener comportamiento normal
                # Los agregamos a una lista temporal para procesarlos con super()
                pass
        
        # Procesar productos sin tracking con comportamiento normal
        normal_procurements = [p for p in procurements if p.product_id.tracking == 'none']
        if normal_procurements:
            normal_merged = super()._get_procurements_to_merge(normal_procurements)
            merged_procurements.extend(normal_merged)
            
        return merged_procurements
    
    def _run_buy(self, procurements):
        """
        Sobrescribir completamente para manejar productos con tracking individualmente
        """
        # Separar procurements por tracking
        tracking_procurements = []
        normal_procurements = []
        
        for procurement in procurements:
            if procurement.product_id.tracking != 'none':
                tracking_procurements.append(procurement)
            else:
                normal_procurements.append(procurement)
        
        # Procesar productos con tracking UNO POR UNO
        for procurement in tracking_procurements:
            _logger.info(f"Procesando individualmente procurement para {procurement.product_id.name}")
            super()._run_buy([procurement])  # Procesar cada uno por separado
        
        # Procesar productos sin tracking normalmente (con agrupamiento)
        if normal_procurements:
            super()._run_buy(normal_procurements)
    
    def _prepare_purchase_order_line(self, product_id, product_qty, product_uom, company_id, values, po):
        """
        Para productos con tracking: SIEMPRE crear nueva línea
        """
        res = super()._prepare_purchase_order_line(product_id, product_qty, product_uom, company_id, values, po)
        
        if product_id.tracking != 'none':
            # FORZAR que sea una nueva línea - eliminar cualquier referencia existente
            res.pop('purchase_line_id', None)
            
            # Forzar cantidad exacta (no permitir agrupamiento de cantidades)
            res['product_qty'] = product_qty
            res['product_uom_qty'] = product_qty
            
            # Propagar campos de mármol
            res.update({
                'marble_height': values.get('marble_height', 0.0),
                'marble_width': values.get('marble_width', 0.0),
                'marble_sqm': values.get('marble_sqm', 0.0),
                'lot_general': values.get('lot_general', ''),
                'bundle_code': values.get('bundle_code', ''),
                'marble_thickness': values.get('marble_thickness', 0.0),
            })
            
            _logger.info(f"Nueva línea PO forzada: {product_id.name} - Qty: {product_qty} - Mármol: {values.get('marble_height')}x{values.get('marble_width')}")
            
        return res
    
    def _find_suitable_po_line(self, procurement, po):
        """
        Para productos con tracking: NUNCA encontrar línea existente
        """
        if procurement.product_id.tracking != 'none':
            _logger.info(f"Producto {procurement.product_id.name} con tracking - NO buscar línea existente")
            return self.env['purchase.order.line']  # Retorna recordset vacío
            
        # Para productos sin tracking, comportamiento normal
        if hasattr(super(), '_find_suitable_po_line'):
            return super()._find_suitable_po_line(procurement, po)
        else:
            return self.env['purchase.order.line']