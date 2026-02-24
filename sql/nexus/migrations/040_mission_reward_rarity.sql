-- Migration 040: Add rarity tags to AI Daily mission reward items
-- Tags each reward item with a rarity level: guaranteed, uncommon, rare, very-rare
-- Also adds the Mork "Mutant Coinage" as guaranteed

DO $$
DECLARE
  _reward_row RECORD;
  _new_items JSONB;
  _item JSONB;
  _item_id INTEGER;
  _rarity TEXT;
  _i INTEGER;

  -- Guaranteed item IDs
  _guaranteed_ids INTEGER[] := ARRAY[1002428, 1000331, 1001546, 1003201];

  -- Uncommon: Stimulants (AccuStim, DevaStim, HyperStim, MediStim, NutriStim 5/10/15mg)
  _uncommon_ids INTEGER[] := ARRAY[
    10000019, 10000020, 10000021,
    10000024, 10000025, 10000026,
    10000030, 10000031, 10000032,
    10000038, 10000039, 10000040,
    10000072, 10000073, 10000074
  ];

  -- Rare: Neurobiotic Boosters
  _rare_ids INTEGER[] := ARRAY[
    10000044, 10000045, 10000059,
    10000046, 10000047,
    10000048, 10000049,
    10000050, 10000060,
    10000051, 10000052,
    10000053, 10000054, 10000055, 10000056,
    10000057, 10000058, 10000061
  ];

  -- Very Rare: Rings (Aeglic, Ares, Artemic, Athenic, Hermetic + variants)
  _very_rare_ids INTEGER[] := ARRAY[
    8000674, 8000675, 8000676, 8000677, 8000678, 8000679,
    8000680, 8000681, 8000682, 8000683, 8000684, 8000685,
    8000686, 8000687, 8000688, 8000689, 8000690, 8000691,
    8000692, 8000693, 8000694, 8000695, 8000696, 8000697,
    8000698, 8000699, 8000700, 8000701, 8000702, 8000703
  ];
BEGIN
  -- Iterate all MissionRewards rows that have Items
  FOR _reward_row IN
    SELECT mr."Id", mr."Items"
    FROM ONLY "MissionRewards" mr
    JOIN ONLY "Missions" m ON m."Id" = mr."MissionId"
    WHERE mr."Items" IS NOT NULL
      AND jsonb_array_length(mr."Items") > 0
      AND m."Name" LIKE '%(AI Daily)%'
  LOOP
    _new_items := '[]'::jsonb;

    FOR _i IN 0 .. jsonb_array_length(_reward_row."Items") - 1
    LOOP
      _item := _reward_row."Items" -> _i;
      _item_id := (_item ->> 'itemId')::integer;
      _rarity := NULL;

      IF _item_id = ANY(_guaranteed_ids) THEN
        _rarity := 'guaranteed';
      ELSIF _item_id = ANY(_uncommon_ids) THEN
        _rarity := 'uncommon';
      ELSIF _item_id = ANY(_rare_ids) THEN
        _rarity := 'rare';
      ELSIF _item_id = ANY(_very_rare_ids) THEN
        _rarity := 'very-rare';
      END IF;

      IF _rarity IS NOT NULL THEN
        _item := _item || jsonb_build_object('rarity', _rarity);
      END IF;

      _new_items := _new_items || jsonb_build_array(_item);
    END LOOP;

    UPDATE ONLY "MissionRewards"
    SET "Items" = _new_items
    WHERE "Id" = _reward_row."Id";
  END LOOP;
END $$;
