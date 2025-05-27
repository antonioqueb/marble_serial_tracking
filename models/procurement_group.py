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
        normal_procurements = []
        
        for procurement in procurements:
            # Obtener product_id de manera segura
            try:
                if hasattr(procurement, 'product_id'):
                    product_id = procurement.product_id
                else:
                    # Si es una tupla, intentar obtener el product_id
                    product_id = procurement[1] if len(procurement) > 1 else None
                    
                if product_id and product_id.tracking != 'none':
                    # Cada producto con tracking va en su propio grupo (no se agrupa)
                    merged_procurements.append([procurement])
                    _logger.info(f"Producto {product_id.name} con tracking - procesamiento individual")
                else:
                    # Para productos sin tracking, agregar a lista normal
                    normal_procurements.append(procurement)
                    
            except Exception as e:
                _logger.warning(f"Error procesando procurement en merge: {e}, agregando a normal_procurements")
                normal_procurements.append(procurement)
        
        # Procesar productos sin tracking con comportamiento normal
        if normal_procurements:
            try:
                normal_merged = super()._get_procurements_to_merge(normal_procurements)
                merged_procurements.extend(normal_merged)
            except Exception as e:
                _logger.error(f"Error en super()._get_procurements_to_merge: {e}")
                # Fallback: agregar cada procurement normal individualmente
                for proc in normal_procurements:
                    merged_procurements.append([proc])
            
        return merged_procurements
    
    def _run_buy(self, procurements):
        """
        Sobrescribir completamente para manejar productos con tracking individualmente
        """
        # Separar procurements por tracking
        tracking_procurements = []
        normal_procurements = []
        
        for procurement in procurements:
            # Los procurements pueden ser objetos Procurement o tuplas
            # Necesitamos obtener el product_id correctamente
            if hasattr(procurement, 'product_id'):
                product_id = procurement.product_id
            else:
                # Si es una tupla o namedtuple, el product_id podría estar en diferentes posiciones
                try:
                    product_id = procurement.product_id if hasattr(procurement, 'product_id') else procurement[1]
                except (IndexError, AttributeError):
                    _logger.warning(f"No se pudo obtener product_id de procurement: {procurement}")
                    normal_procurements.append(procurement)
                    continue
            
            if product_id.tracking != 'none':
                tracking_procurements.append(procurement)
                _logger.info(f"Procurement con tracking detectado: {product_id.name}")
            else:
                normal_procurements.append(procurement)
        
        # Procesar productos con tracking UNO POR UNO
        for procurement in tracking_procurements:
            try:
                product_name = procurement.product_id.name if hasattr(procurement, 'product_id') else procurement[1].name
                _logger.info(f"Procesando individualmente procurement para {product_name}")
                super()._run_buy([procurement])  # Procesar cada uno por separado
            except Exception as e:
                _logger.error(f"Error procesando procurement individual: {e}")
                # Si falla, procesarlo con el método normal
                normal_procurements.append(procurement)
        
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
        try:
            # Obtener product_id de manera segura
            if hasattr(procurement, 'product_id'):
                product_id = procurement.product_id
            else:
                product_id = procurement[1] if len(procurement) > 1 else None
                
            if product_id and product_id.tracking != 'none':
                _logger.info(f"Producto {product_id.name} con tracking - NO buscar línea existente")
                return self.env['purchase.order.line']  # Retorna recordset vacío
                
        except Exception as e:
            _logger.warning(f"Error en _find_suitable_po_line: {e}")
            
        # Para productos sin tracking, comportamiento normal
        if hasattr(super(), '_find_suitable_po_line'):
            return super()._find_suitable_po_line(procurement, po)
        else:
            return self.env['purchase.order.line']