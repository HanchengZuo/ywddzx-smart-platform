-- Consolidate legacy per-cell video shelf cards without deleting plans or audit history.
DO $$
DECLARE bundle RECORD;
BEGIN
  FOR bundle IN
    SELECT MIN(id) AS keeper, ARRAY_AGG(id ORDER BY id) AS ids
    FROM inspection_schedule_shelf
    WHERE mode='online' AND status='waiting' AND jsonb_array_length(inspector_ids)=1
    GROUP BY scheduled_date,source_station_id,source_station_name,inspector_ids
    HAVING BOOL_OR(source_column_key<>'row')
  LOOP
    INSERT INTO inspection_schedule_shelf_events(shelf_id,action,details,actor_name)
    SELECT id,'row_upgrade',jsonb_build_object('merged_into',bundle.keeper,
      'merged_ids',to_jsonb(bundle.ids),'before_column_key',source_column_key), '系统升级'
    FROM inspection_schedule_shelf WHERE id=ANY(bundle.ids);
    UPDATE inspection_schedule_shelf SET source_column_key='row',revision=revision+1,
      updated_by=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=bundle.keeper;
    UPDATE inspection_schedule_shelf SET status='discarded',revision=revision+1,
      updated_by=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=ANY(bundle.ids) AND id<>bundle.keeper;
  END LOOP;
END $$;
