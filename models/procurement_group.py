# models/procurement_group.py
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class StockRule(models.Model):
    _inherit = 'stock.rule'
    
    def _run_buy(self, procurements):
        """
        Sobrescribir para asegurar que marble_sqm se propague correctamente
        """
        _logger.info(f"[MARBLE-PROCUREMENT] Ejecutando _run_buy para {len(procurements)} procurements")
        
        # Capturar los valores ANTES de llamar al método padre
        procurement_data = {}
        for procurement in procurements:
            # procurement es un namedtuple: (product, qty, uom, location, name, origin, company, values)
            try:
                product = procurement.product_id
                origin = procurement.origin  
                values = procurement.values or {}
            except AttributeError:
                # Fallback para acceso por índice si no es namedtuple
                product = procurement[0]
                origin = procurement[5] 
                values = procurement[7] if len(procurement) > 7 else {}
            
            if 'marble_sqm' in values and values.get('marble_sqm', 0.0) > 0:
                # Crear una clave única para este procurement
                proc_key = f"{product.id}_{origin}"  # product_id_origin
                procurement_data[proc_key] = {
                    'marble_height': values.get('marble_height', 0.0),
                    'marble_width': values.get('marble_width', 0.0),
                    'marble_sqm': values.get('marble_sqm', 0.0),
                    'lot_general': values.get('lot_general', ''),
                    'marble_thickness': values.get('marble_thickness', 0.0),
                }
                _logger.info(f"[MARBLE-PROCUREMENT] Capturado para {product.name}: {procurement_data[proc_key]}")

        # Llamar al método padre para crear/actualizar las PO
        res = super()._run_buy(procurements)
        
        # DESPUÉS de crear las PO, buscar y actualizar las líneas
        for procurement in procurements:
            try:
                product = procurement.product_id
                origin = procurement.origin  
                values = procurement.values or {}
            except AttributeError:
                # Fallback para acceso por índice si no es namedtuple
                product = procurement[0]
                origin = procurement[5] 
                values = procurement[7] if len(procurement) > 7 else {}
                
            proc_key = f"{product.id}_{origin}"
            
            if proc_key in procurement_data:
                marble_data = procurement_data[proc_key]
                
                # Buscar la línea de PO que se acaba de crear/actualizar
                # mediante el move_dest_ids que se acaba de vincular
                if 'move_dest_ids' in values:
                    move_dest = values.get('move_dest_ids')
                    if move_dest:
                        # Buscar líneas de PO vinculadas a este movimiento
                        po_lines = self.env['purchase.order.line'].search([
                            ('move_dest_ids', 'in', move_dest.ids if hasattr(move_dest, 'ids') else [move_dest.id])
                        ])
                        
                        _logger.info(f"[MARBLE-PROCUREMENT] Encontradas {len(po_lines)} PO lines para actualizar")
                        
                        for po_line in po_lines:
                            _logger.info(f"[MARBLE-PROCUREMENT] Actualizando PO line {po_line.id} con: {marble_data}")
                            
                            # Actualizar con contexto especial para evitar que el compute sobreescriba
                            po_line.with_context(from_procurement=True).write(marble_data)
                            
                            # Verificar que se guardó correctamente
                            po_line.refresh()
                            _logger.info(f"[MARBLE-PROCUREMENT] PO line {po_line.id} después de actualizar: m²={po_line.marble_sqm}")

        return res
    
    def _prepare_purchase_order_line(self, product_id, product_qty, product_uom, company_id, values, po):
        """
        Asegurar que el campo marble_sqm se propague a las líneas de PO nuevas
        """
        _logger.info(f"[MARBLE-PREPARE] Preparando PO line para {product_id.name}")
        _logger.info(f"[MARBLE-PREPARE] Values completos: {values}")
        
        res = super()._prepare_purchase_order_line(product_id, product_qty, product_uom, company_id, values, po)
        
        # Propagar TODOS los campos de mármol si existen en values
        marble_fields = {
            'marble_height': values.get('marble_height', 0.0),
            'marble_width': values.get('marble_width', 0.0),
            'marble_sqm': values.get('marble_sqm', 0.0),
            'lot_general': values.get('lot_general', ''),
            'marble_thickness': values.get('marble_thickness', 0.0),
        }
        
        # Solo agregar si al menos uno tiene valor
        if any(v for v in marble_fields.values() if v):
            res.update(marble_fields)
            _logger.info(f"[MARBLE-PREPARE] Campos de mármol agregados: {marble_fields}")
        
        return res