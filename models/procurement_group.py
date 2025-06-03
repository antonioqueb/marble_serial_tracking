# models/procurement_group.py
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _run_buy(self, procurements): # procurements es una lista de tuplas (procurement_request, rule)
        _logger.info(f"[MARBLE-PROCUREMENT] Ejecutando _run_buy para {len(procurements)} procurements")
        procurement_data_to_apply = {} # {proc_key: marble_data_dict}
        # Nuevo: mapeo de proc_key a los valores originales del procurement_request para _prepare_purchase_order_line
        original_proc_values_map = {} 

        # BUCLE 1: Extraer y almacenar los datos de mármol
        for procurement_request, rule in procurements:
            if not hasattr(procurement_request, 'product_id') or \
               not hasattr(procurement_request, 'origin') or \
               not hasattr(procurement_request, 'values'):
                _logger.warning(f"[MARBLE-PROCUREMENT] BUCLE 1: procurement_request con formato inesperado: {procurement_request}. Omitiendo.")
                continue

            product_record = procurement_request.product_id
            origin_str = procurement_request.origin # Este es el SO (ej. S00002)
            
            # procurement_request.values es el diccionario de valores que llega a _run_buy.
            # Este es el que vimos en el log que NO contenía marble_sqm.
            current_proc_values = procurement_request.values or {}
            _logger.info(f"[MARBLE-PROCUREMENT] BUCLE 1: Origen: {origin_str}, Producto: {product_record.name}, Valores en procurement_request.values: {current_proc_values}")

            proc_key = f"{product_record.id}_{origin_str}"
            original_proc_values_map[proc_key] = current_proc_values # Guardamos los valores que SÍ llegan

            marble_data_found = {}
            
            # Intento 1: ¿Están los campos de mármol directamente en current_proc_values? (Probablemente no según tus logs)
            if 'marble_sqm' in current_proc_values and current_proc_values.get('marble_sqm', 0.0) > 0:
                marble_data_found = {
                    'marble_height': current_proc_values.get('marble_height', 0.0),
                    'marble_width': current_proc_values.get('marble_width', 0.0),
                    'marble_sqm': current_proc_values.get('marble_sqm', 0.0),
                    'lot_general': current_proc_values.get('lot_general', ''),
                    'marble_thickness': current_proc_values.get('marble_thickness', 0.0),
                }
                _logger.info(f"[MARBLE-PROCUREMENT] BUCLE 1: Datos de mármol encontrados directamente en current_proc_values para {proc_key}: {marble_data_found}")
            
            # Intento 2: Si no, intentar obtenerlos del stock.move de origen (move_dest_ids)
            # Esto asume que el procurement de compra se generó a partir de un stock.move (MTO)
            if not marble_data_found and 'move_dest_ids' in current_proc_values and current_proc_values['move_dest_ids']:
                # move_dest_ids suele ser un recordset de stock.move
                # En el contexto de _run_buy, move_dest_ids son los moves que *necesitan* este producto que se va a comprar.
                # Estos moves deberían tener los campos de mármol si se propagaron correctamente desde la SO.
                source_moves = current_proc_values['move_dest_ids']
                if isinstance(source_moves, models.BaseModel) and source_moves._name == 'stock.move':
                    # Tomamos del primer move, asumiendo que los datos son consistentes si hay varios
                    # o que el procurement es para un move específico.
                    # Para MTO de venta, suele ser un solo move.
                    first_move = source_moves[0] if source_moves else None
                    if first_move and first_move.marble_sqm > 0: # Chequeamos si el move tiene los m2
                        marble_data_found = {
                            'marble_height': first_move.marble_height,
                            'marble_width': first_move.marble_width,
                            'marble_sqm': first_move.marble_sqm,
                            'lot_general': first_move.lot_general,
                            'marble_thickness': first_move.marble_thickness,
                        }
                        _logger.info(f"[MARBLE-PROCUREMENT] BUCLE 1: Datos de mármol encontrados en el move de origen {first_move.name} (ID: {first_move.id}) para {proc_key}: {marble_data_found}")
                        
                        # IMPORTANTE: Añadir estos datos al diccionario original_proc_values_map[proc_key]
                        # para que _prepare_purchase_order_line los reciba.
                        original_proc_values_map[proc_key].update(marble_data_found)
                        _logger.info(f"[MARBLE-PROCUREMENT] BUCLE 1: original_proc_values_map actualizado para {proc_key}: {original_proc_values_map[proc_key]}")


            if marble_data_found:
                procurement_data_to_apply[proc_key] = marble_data_found
            else:
                _logger.warning(f"[MARBLE-PROCUREMENT] BUCLE 1: No se capturaron datos de mármol para {proc_key} ni en current_proc_values ni en moves de origen.")
        
        # Pasar el mapa de valores originales al contexto para que _prepare_purchase_order_line lo use
        self = self.with_context(original_proc_values_map=original_proc_values_map)
        
        res = super(StockRule, self)._run_buy(procurements) # Llamar a super con el contexto modificado

        # BUCLE 2: Aplicar/Reafirmar los datos de mármol a las PO Lines.
        if procurement_data_to_apply:
            _logger.info(f"[MARBLE-PROCUREMENT] BUCLE 2: Iniciando aplicación de datos de mármol a PO Lines. Datos capturados: {procurement_data_to_apply}")
            for procurement_request, rule in procurements:
                # ... (resto del Bucle 2 como lo tenías, pero asegurándote que usa 'proc_key' bien definido)
                if not hasattr(procurement_request, 'product_id') or not hasattr(procurement_request, 'origin'):
                    continue
                product_record = procurement_request.product_id
                origin_str = procurement_request.origin
                proc_key = f"{product_record.id}_{origin_str}"

                if proc_key in procurement_data_to_apply:
                    marble_data = procurement_data_to_apply[proc_key]
                    # 'current_proc_values' aquí son los valores del procurement_request que entró a _run_buy
                    current_proc_values = procurement_request.values or {} 
                    move_dest_ids_val = current_proc_values.get('move_dest_ids')

                    if move_dest_ids_val:
                        # ... (lógica para obtener actual_move_ids y po_lines como antes) ...
                        actual_move_ids = []
                        if isinstance(move_dest_ids_val, models.BaseModel):
                            actual_move_ids = move_dest_ids_val.ids
                        elif isinstance(move_dest_ids_val, (list, tuple)) and all(isinstance(i, int) for i in move_dest_ids_val):
                            actual_move_ids = list(move_dest_ids_val)
                        elif isinstance(move_dest_ids_val, int):
                            actual_move_ids = [move_dest_ids_val]
                        
                        if not actual_move_ids:
                            _logger.info(f"[MARBLE-PROCUREMENT] BUCLE 2: No hay move_dest_ids concretos para buscar PO lines para proc_key {proc_key}")
                            continue

                        po_lines = self.env['purchase.order.line'].search([
                            ('move_dest_ids', 'in', actual_move_ids)
                        ])

                        if not po_lines:
                            _logger.info(f"[MARBLE-PROCUREMENT] BUCLE 2: No se encontraron líneas de PO para move_dest_ids {actual_move_ids} (proc_key {proc_key})")
                        else:
                            for po_line in po_lines:
                                _logger.info(f"[MARBLE-PROCUREMENT] BUCLE 2: Actualizando PO line {po_line.id} (Orden: {po_line.order_id.name}) con: {marble_data}")
                                po_line.with_context(from_procurement=True).write(marble_data)
                                po_line.refresh()
                                _logger.info(f"[MARBLE-PROCUREMENT] BUCLE 2: PO line {po_line.id} DESPUÉS de actualizar: m²={po_line.marble_sqm}")
                    else:
                         _logger.info(f"[MARBLE-PROCUREMENT] BUCLE 2: No hay 'move_dest_ids' en current_proc_values para proc_key {proc_key}. No se pueden encontrar PO lines por esta vía.")
        else:
            _logger.info("[MARBLE-PROCUREMENT] BUCLE 2: No hay datos de mármol capturados para aplicar a PO Lines.")
            
        return res

    def _prepare_purchase_order_line(self, product_id, product_qty, product_uom, company_id, values, po):
        # 'values' aquí es el procurement_request.values que entró a _run_buy.
        # Necesitamos acceder a los valores enriquecidos que preparamos en _run_buy.
        
        origin_str = values.get('origin') # El origin del procurement_request
        proc_key = f"{product_id.id}_{origin_str}"
        
        original_proc_values_map = self.env.context.get('original_proc_values_map', {})
        # Usar los valores enriquecidos del mapa si existen para esta clave, sino los 'values' directos.
        # Esto es CRUCIAL: 'values_for_po_line' ahora debería tener los campos de mármol si los encontramos en el Bucle 1 de _run_buy.
        values_for_po_line = original_proc_values_map.get(proc_key, values) 

        _logger.info(f"[MARBLE-PREPARE] Iniciando para producto {product_id.name}, PO: {po.name if po else 'Nueva PO'}, ProcOrigin: {origin_str}, ProcKey: {proc_key}")
        _logger.info(f"[MARBLE-PREPARE] 'values' directos recibidos: {values}")
        _logger.info(f"[MARBLE-PREPARE] 'values_for_po_line' (potencialmente enriquecidos): {values_for_po_line}")

        # Llamar a super con los 'values' originales, ya que super no conocerá nuestros campos de mármol.
        # Los campos de mármol los añadiremos nosotros después.
        res = super()._prepare_purchase_order_line(product_id, product_qty, product_uom, company_id, values, po)
        _logger.info(f"[MARBLE-PREPARE] Valores de res DESPUÉS de super(): {res}")

        marble_fields_to_set = {}
        # Ahora usamos 'values_for_po_line' que debería tener los datos de mármol.
        if values_for_po_line.get('marble_sqm', 0.0) > 0:
            marble_fields_to_set['marble_sqm'] = values_for_po_line.get('marble_sqm', 0.0)
            marble_fields_to_set['marble_height'] = values_for_po_line.get('marble_height', 0.0)
            marble_fields_to_set['marble_width'] = values_for_po_line.get('marble_width', 0.0)
            marble_fields_to_set['lot_general'] = values_for_po_line.get('lot_general', '')
            marble_fields_to_set['marble_thickness'] = values_for_po_line.get('marble_thickness', 0.0)

        if marble_fields_to_set:
            _logger.info(f"[MARBLE-PREPARE] Aplicando campos de mármol a res: {marble_fields_to_set}")
            res.update(marble_fields_to_set)
        else:
            _logger.info(f"[MARBLE-PREPARE] No se aplicaron campos de mármol a res (marble_sqm no era > 0 en values_for_po_line o no estaba presente).")

        _logger.info(f"[MARBLE-PREPARE] Valores de res ANTES de return: {res}")
        return res