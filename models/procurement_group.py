from odoo import models, api

class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _run_buy(self, procurements):  # procurements es una lista de tuplas (procurement_request, rule)
        procurement_data_to_apply = {}  # {proc_key: marble_data_dict}
        # Nuevo: mapeo de proc_key a los valores originales del procurement_request para _prepare_purchase_order_line
        original_proc_values_map = {}

        # BUCLE 1: Extraer y almacenar los datos de mármol
        for procurement_request, rule in procurements:
            if not hasattr(procurement_request, 'product_id') or \
               not hasattr(procurement_request, 'origin') or \
               not hasattr(procurement_request, 'values'):
                continue

            product_record = procurement_request.product_id
            origin_str = procurement_request.origin  # Este es el SO (ej. S00002)

            # procurement_request.values es el diccionario de valores que llega a _run_buy.
            current_proc_values = procurement_request.values or {}

            proc_key = f"{product_record.id}_{origin_str}"
            original_proc_values_map[proc_key] = current_proc_values  # Guardamos los valores que SÍ llegan

            marble_data_found = {}

            # Intento 1: ¿Están los campos de mármol directamente en current_proc_values?
            if 'marble_sqm' in current_proc_values and current_proc_values.get('marble_sqm', 0.0) > 0:
                marble_data_found = {
                    'marble_height': current_proc_values.get('marble_height', 0.0),
                    'marble_width': current_proc_values.get('marble_width', 0.0),
                    'marble_sqm': current_proc_values.get('marble_sqm', 0.0),
                    'lot_general': current_proc_values.get('lot_general', ''),
                    'marble_thickness': current_proc_values.get('marble_thickness', 0.0),
                    'numero_contenedor': current_proc_values.get('numero_contenedor', ''),
                }

            # Intento 2: Si no, intentar obtenerlos del stock.move de origen (move_dest_ids)
            if not marble_data_found and 'move_dest_ids' in current_proc_values and current_proc_values['move_dest_ids']:
                source_moves = current_proc_values['move_dest_ids']
                if isinstance(source_moves, models.BaseModel) and source_moves._name == 'stock.move':
                    first_move = source_moves[0] if source_moves else None
                    if first_move and first_move.marble_sqm > 0:  # Chequeamos si el move tiene los m2
                        marble_data_found = {
                            'marble_height': first_move.marble_height,
                            'marble_width': first_move.marble_width,
                            'marble_sqm': first_move.marble_sqm,
                            'lot_general': first_move.lot_general,
                            'marble_thickness': first_move.marble_thickness,
                            'numero_contenedor': first_move.numero_contenedor,
                            
                        }
                        # IMPORTANTE: Añadir estos datos al diccionario original_proc_values_map[proc_key]
                        original_proc_values_map[proc_key].update(marble_data_found)

            if marble_data_found:
                procurement_data_to_apply[proc_key] = marble_data_found

        # Pasar el mapa de valores originales al contexto para que _prepare_purchase_order_line lo use
        self_with_context = self.with_context(original_proc_values_map=original_proc_values_map)

        res = super(StockRule, self_with_context)._run_buy(procurements)  # Llamar a super con el contexto modificado

        # BUCLE 2: Aplicar/Reafirmar los datos de mármol a las PO Lines.
        if procurement_data_to_apply:
            for procurement_request, rule in procurements:
                if not hasattr(procurement_request, 'product_id') or not hasattr(procurement_request, 'origin'):
                    continue
                product_record = procurement_request.product_id
                origin_str = procurement_request.origin
                proc_key = f"{product_record.id}_{origin_str}"

                if proc_key in procurement_data_to_apply:
                    marble_data = procurement_data_to_apply[proc_key]
                    current_proc_values = procurement_request.values or {}
                    move_dest_ids_val = current_proc_values.get('move_dest_ids')

                    if move_dest_ids_val:
                        actual_move_ids = []
                        # Asegurarse de que move_dest_ids_val es un iterable de IDs
                        if isinstance(move_dest_ids_val, models.BaseModel):  # Si es un recordset
                            actual_move_ids = move_dest_ids_val.ids
                        elif isinstance(move_dest_ids_val, (list, tuple)) and all(isinstance(i, int) for i in move_dest_ids_val):  # Si es una lista/tupla de IDs
                            actual_move_ids = list(move_dest_ids_val)
                        elif isinstance(move_dest_ids_val, int):  # Si es un solo ID
                            actual_move_ids = [move_dest_ids_val]

                        if not actual_move_ids:
                            continue

                        po_lines = self.env['purchase.order.line'].search([
                            ('move_dest_ids', 'in', actual_move_ids)
                        ])

                        if po_lines:
                            for po_line in po_lines:
                                po_line.with_context(from_procurement=True).write(marble_data)
        return res

    def _prepare_purchase_order_line(self, product_id, product_qty, product_uom, company_id, values, po):
        origin_str = values.get('origin')  # El origin del procurement_request
        proc_key = f"{product_id.id}_{origin_str}"

        original_proc_values_map = self.env.context.get('original_proc_values_map', {})
        # Usar los valores enriquecidos del mapa si existen para esta clave, sino los 'values' directos.
        values_for_po_line = original_proc_values_map.get(proc_key, values)

        # Llamar a super con los 'values' originales.
        res_vals = super()._prepare_purchase_order_line(product_id, product_qty, product_uom, company_id, values, po)

        marble_fields_to_set = {}
        # Ahora usamos 'values_for_po_line' que debería tener los datos de mármol.
        if values_for_po_line.get('marble_sqm', 0.0) > 0:  # Condición principal para aplicar datos de mármol
            marble_fields_to_set['marble_sqm'] = values_for_po_line.get('marble_sqm', 0.0)
            marble_fields_to_set['marble_height'] = values_for_po_line.get('marble_height', 0.0)
            marble_fields_to_set['marble_width'] = values_for_po_line.get('marble_width', 0.0)
            marble_fields_to_set['lot_general'] = values_for_po_line.get('lot_general', '')
            marble_fields_to_set['marble_thickness'] = values_for_po_line.get('marble_thickness', 0.0)
            marble_fields_to_set['numero_contenedor'] = values_for_po_line.get('numero_contenedor', '')
        if marble_fields_to_set:
            res_vals.update(marble_fields_to_set)

        return res_vals
