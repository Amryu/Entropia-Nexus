-- Migration 133: Seed the Fishing guide (category, chapters, lessons, paragraphs).
--
-- Idempotent: re-running upserts the lesson rows by their UNIQUE slug, refreshes
-- titles / chapter assignments / sort orders, and replaces each lesson's
-- paragraphs wholesale. Category and chapters are matched by title within their
-- parent (no UNIQUE index there, so we look-up-or-create).
--
-- Safe to re-run after editing the HTML below to push content updates without
-- losing the existing IDs that the SvelteKit page references via slug.

BEGIN;

DO $mig$
DECLARE
  v_category_id   integer;
  v_intro_id      integer;
  v_equipment_id  integer;
  v_minigames_id  integer;
  v_environment_id integer;
  v_species_id    integer;
  v_materials_id  integer;
  v_lesson_id     integer;
BEGIN
  -- ============================================================
  -- Category
  -- ============================================================
  SELECT id INTO v_category_id
    FROM guide_categories
   WHERE title = 'Fishing'
   LIMIT 1;

  IF v_category_id IS NULL THEN
    INSERT INTO guide_categories (title, description, sort_order)
    VALUES (
      'Fishing',
      'End-to-end guide to fishing in Entropia Universe: gear, mini-games, biomes, fish species, and refining.',
      100
    )
    RETURNING id INTO v_category_id;
  ELSE
    UPDATE guide_categories
       SET description = 'End-to-end guide to fishing in Entropia Universe: gear, mini-games, biomes, fish species, and refining.',
           updated_at  = now()
     WHERE id = v_category_id;
  END IF;

  -- ============================================================
  -- Chapters (find-or-create by title within this category)
  -- ============================================================
  SELECT id INTO v_intro_id FROM guide_chapters WHERE category_id = v_category_id AND title = 'Introduction' LIMIT 1;
  IF v_intro_id IS NULL THEN
    INSERT INTO guide_chapters (category_id, title, description, sort_order)
    VALUES (v_category_id, 'Introduction', 'What fishing is and which professions cover it.', 0)
    RETURNING id INTO v_intro_id;
  END IF;

  SELECT id INTO v_equipment_id FROM guide_chapters WHERE category_id = v_category_id AND title = 'Equipment' LIMIT 1;
  IF v_equipment_id IS NULL THEN
    INSERT INTO guide_chapters (category_id, title, description, sort_order)
    VALUES (v_category_id, 'Equipment', 'Fishing rods and the four attachment slots.', 1)
    RETURNING id INTO v_equipment_id;
  END IF;

  SELECT id INTO v_minigames_id FROM guide_chapters WHERE category_id = v_category_id AND title = 'Mini-games' LIMIT 1;
  IF v_minigames_id IS NULL THEN
    INSERT INTO guide_chapters (category_id, title, description, sort_order)
    VALUES (v_category_id, 'Mini-games', 'How each fishing type plays out, including stamina and enrage mechanics.', 2)
    RETURNING id INTO v_minigames_id;
  END IF;

  SELECT id INTO v_environment_id FROM guide_chapters WHERE category_id = v_category_id AND title = 'Environmental Factors' LIMIT 1;
  IF v_environment_id IS NULL THEN
    INSERT INTO guide_chapters (category_id, title, description, sort_order)
    VALUES (v_category_id, 'Environmental Factors', 'Biomes, hot spots, time of day, depth, planet, and rod-type gating.', 3)
    RETURNING id INTO v_environment_id;
  END IF;

  SELECT id INTO v_species_id FROM guide_chapters WHERE category_id = v_category_id AND title = 'Fish Species' LIMIT 1;
  IF v_species_id IS NULL THEN
    INSERT INTO guide_chapters (category_id, title, description, sort_order)
    VALUES (v_category_id, 'Fish Species', 'The ten known fish species and where to find them.', 4)
    RETURNING id INTO v_species_id;
  END IF;

  SELECT id INTO v_materials_id FROM guide_chapters WHERE category_id = v_category_id AND title = 'Material Usage' LIMIT 1;
  IF v_materials_id IS NULL THEN
    INSERT INTO guide_chapters (category_id, title, description, sort_order)
    VALUES (v_category_id, 'Material Usage', 'Refining caught fish, AI dailies, and quick-reference tips.', 5)
    RETURNING id INTO v_materials_id;
  END IF;

  -- Keep chapter sort_order / description fresh in case prior runs landed early drafts.
  UPDATE guide_chapters SET sort_order = 0, description = 'What fishing is and which professions cover it.', updated_at = now() WHERE id = v_intro_id;
  UPDATE guide_chapters SET sort_order = 1, description = 'Fishing rods and the four attachment slots.', updated_at = now() WHERE id = v_equipment_id;
  UPDATE guide_chapters SET sort_order = 2, description = 'How each fishing type plays out, including stamina and enrage mechanics.', updated_at = now() WHERE id = v_minigames_id;
  UPDATE guide_chapters SET sort_order = 3, description = 'Biomes, hot spots, time of day, depth, planet, and rod-type gating.', updated_at = now() WHERE id = v_environment_id;
  UPDATE guide_chapters SET sort_order = 4, description = 'The ten known fish species and where to find them.', updated_at = now() WHERE id = v_species_id;
  UPDATE guide_chapters SET sort_order = 5, description = 'Refining caught fish, AI dailies, and quick-reference tips.', updated_at = now() WHERE id = v_materials_id;

  -- ============================================================
  -- Lessons + paragraphs
  -- Each lesson: ON CONFLICT (slug) upsert -> capture id -> replace paragraphs.
  -- ============================================================

  ---------- Chapter 1: Introduction ----------

  INSERT INTO guide_lessons (chapter_id, title, slug, sort_order)
  VALUES (v_intro_id, 'Overview', 'fishing-overview', 0)
  ON CONFLICT (slug) DO UPDATE
    SET chapter_id = EXCLUDED.chapter_id,
        title      = EXCLUDED.title,
        sort_order = EXCLUDED.sort_order,
        updated_at = now()
  RETURNING id INTO v_lesson_id;
  DELETE FROM guide_paragraphs WHERE lesson_id = v_lesson_id;
  INSERT INTO guide_paragraphs (lesson_id, content_html, sort_order) VALUES (v_lesson_id,
$html$
<p>Fishing is a resource-collecting activity built around four mini-games: <strong>Angling</strong>, <strong>Casting</strong>, <strong>Fly Fishing</strong>, and <strong>Deep Ocean</strong>. Your rod choice determines which mini-game you play and which profession ticks up. Attachments shape difficulty, reach, and what bites.</p>
<p>The five fishing professions are:</p>
<ul>
  <li><a href="/information/professions/Cast%20Fisher">Cast Fisher</a> - rod-and-line casting from shore.</li>
  <li><a href="/information/professions/Baiter">Baiter</a> - bait-on-hook angling.</li>
  <li><a href="/information/professions/Fly%20Fisher">Fly Fisher</a> - lure / fly-imitation angling.</li>
  <li><a href="/information/professions/Deep%20Ocean%20Fisher">Deep Ocean Fisher</a> - boat-only deep-water casting.</li>
  <li><a href="/information/professions/Baitfisher">Baitfisher</a> - free-to-use baitfishing for Spool Cell production.</li>
</ul>
<p>Caught fish exist as both <strong>materials</strong> (refinable) and <strong>information entries</strong> with biome, depth, and rod-type data. Browse the full list at <a href="/information/fishes">Information &gt; Fishes</a>.</p>$html$, 0);

  ---------- Chapter 2: Equipment ----------

  INSERT INTO guide_lessons (chapter_id, title, slug, sort_order)
  VALUES (v_equipment_id, 'Fishing Rods', 'fishing-rods', 0)
  ON CONFLICT (slug) DO UPDATE
    SET chapter_id = EXCLUDED.chapter_id,
        title      = EXCLUDED.title,
        sort_order = EXCLUDED.sort_order,
        updated_at = now()
  RETURNING id INTO v_lesson_id;
  DELETE FROM guide_paragraphs WHERE lesson_id = v_lesson_id;
  INSERT INTO guide_paragraphs (lesson_id, content_html, sort_order) VALUES (v_lesson_id,
$html$
<p>The rod is the foundation of any fishing setup. Browse the full catalogue at <a href="/items/tools/fishingrods">Items &gt; Tools &gt; Fishing Rods</a>.</p>
<p>Each rod determines:</p>
<ul>
  <li><strong>Fishing type</strong> - Angling, Casting, Fly Fishing, or Deep Ocean.</li>
  <li><strong>Profession</strong> that gains skill from each cast.</li>
  <li><strong>Base stats</strong> (Strength and Flexibility) used by the mini-games.</li>
  <li><strong>Ammo burn rate</strong> per attempt.</li>
  <li><strong>Skill interval</strong> - how often skill ticks fire.</li>
</ul>
<p>Rods accept <strong>four attachment slots</strong>: a Reel, a Blank, a Line, and a Lure. The next four lessons cover each.</p>$html$, 0);

  INSERT INTO guide_lessons (chapter_id, title, slug, sort_order)
  VALUES (v_equipment_id, 'Reels', 'fishing-reels', 1)
  ON CONFLICT (slug) DO UPDATE
    SET chapter_id = EXCLUDED.chapter_id,
        title      = EXCLUDED.title,
        sort_order = EXCLUDED.sort_order,
        updated_at = now()
  RETURNING id INTO v_lesson_id;
  DELETE FROM guide_paragraphs WHERE lesson_id = v_lesson_id;
  INSERT INTO guide_paragraphs (lesson_id, content_html, sort_order) VALUES (v_lesson_id,
$html$
<p>Reels add Strength plus a unique <strong>Speed</strong> stat. Browse them at <a href="/items/attachments/fishingreels">Items &gt; Attachments &gt; Fishing Reels</a>.</p>
<ul>
  <li>In <strong>Angling</strong>, higher Speed appears to make the bar move faster.</li>
  <li>In <strong>Casting</strong>, Speed likely contributes to reeling alongside Strength during the catch phase.</li>
</ul>$html$, 0);

  INSERT INTO guide_lessons (chapter_id, title, slug, sort_order)
  VALUES (v_equipment_id, 'Lines', 'fishing-lines', 2)
  ON CONFLICT (slug) DO UPDATE
    SET chapter_id = EXCLUDED.chapter_id,
        title      = EXCLUDED.title,
        sort_order = EXCLUDED.sort_order,
        updated_at = now()
  RETURNING id INTO v_lesson_id;
  DELETE FROM guide_paragraphs WHERE lesson_id = v_lesson_id;
  INSERT INTO guide_paragraphs (lesson_id, content_html, sort_order) VALUES (v_lesson_id,
$html$
<p>Lines add Strength and Flexibility plus a unique <strong>Line Length</strong> stat. Browse them at <a href="/items/attachments/fishinglines">Items &gt; Attachments &gt; Fishing Lines</a>.</p>
<ul>
  <li>In <strong>Casting</strong>, Length sets the total bar length of the catch mini-game - a longer line means a longer bar to drag the fish across.</li>
  <li>The role in Angling is currently unconfirmed.</li>
</ul>$html$, 0);

  INSERT INTO guide_lessons (chapter_id, title, slug, sort_order)
  VALUES (v_equipment_id, 'Blanks', 'fishing-blanks', 3)
  ON CONFLICT (slug) DO UPDATE
    SET chapter_id = EXCLUDED.chapter_id,
        title      = EXCLUDED.title,
        sort_order = EXCLUDED.sort_order,
        updated_at = now()
  RETURNING id INTO v_lesson_id;
  DELETE FROM guide_paragraphs WHERE lesson_id = v_lesson_id;
  INSERT INTO guide_paragraphs (lesson_id, content_html, sort_order) VALUES (v_lesson_id,
$html$
<p>Blanks are pure stat sticks - they add Strength and Flexibility with no unique mechanic. Browse them at <a href="/items/attachments/fishingblanks">Items &gt; Attachments &gt; Fishing Blanks</a>.</p>$html$, 0);

  INSERT INTO guide_lessons (chapter_id, title, slug, sort_order)
  VALUES (v_equipment_id, 'Lures', 'fishing-lures', 4)
  ON CONFLICT (slug) DO UPDATE
    SET chapter_id = EXCLUDED.chapter_id,
        title      = EXCLUDED.title,
        sort_order = EXCLUDED.sort_order,
        updated_at = now()
  RETURNING id INTO v_lesson_id;
  DELETE FROM guide_paragraphs WHERE lesson_id = v_lesson_id;
  INSERT INTO guide_paragraphs (lesson_id, content_html, sort_order) VALUES (v_lesson_id,
$html$
<p>Lures carry two unique stats. Browse them at <a href="/items/attachments/fishinglures">Items &gt; Attachments &gt; Fishing Lures</a>.</p>
<ul>
  <li><strong>Quality</strong> - speeds up how quickly a fish bites.</li>
  <li><strong>Depth</strong> - unlocks fish that only appear past a minimum depth.</li>
</ul>
<p>Lure <em>type</em> probably skews which fish bite most often, but no fish has yet been confirmed as locked behind a single lure type.</p>$html$, 0);

  ---------- Chapter 3: Mini-games ----------

  INSERT INTO guide_lessons (chapter_id, title, slug, sort_order)
  VALUES (v_minigames_id, 'Angling', 'fishing-angling', 0)
  ON CONFLICT (slug) DO UPDATE
    SET chapter_id = EXCLUDED.chapter_id,
        title      = EXCLUDED.title,
        sort_order = EXCLUDED.sort_order,
        updated_at = now()
  RETURNING id INTO v_lesson_id;
  DELETE FROM guide_paragraphs WHERE lesson_id = v_lesson_id;
  INSERT INTO guide_paragraphs (lesson_id, content_html, sort_order) VALUES (v_lesson_id,
$html$
<p>Profession: <a href="/information/professions/Baiter">Baiter</a>. Skill: <a href="/information/skills/Angling">Angling</a>.</p>
<p>A "chase the fish" mini-game. A bar moves around; you keep your indicator on the fish to fill a progress meter.</p>
<ul>
  <li><strong>Strength</strong> drives how fast the meter fills while you're on the fish.</li>
  <li><strong>Flexibility</strong> likely reduces the negative progress incurred while off the fish.</li>
  <li>The fish can <strong>enrage</strong> at any moment, doubling its speed and moving erratically. Enrages early - while the meter is still low - are the most common cause of failed catches.</li>
</ul>$html$, 0);

  INSERT INTO guide_lessons (chapter_id, title, slug, sort_order)
  VALUES (v_minigames_id, 'Casting', 'fishing-casting', 1)
  ON CONFLICT (slug) DO UPDATE
    SET chapter_id = EXCLUDED.chapter_id,
        title      = EXCLUDED.title,
        sort_order = EXCLUDED.sort_order,
        updated_at = now()
  RETURNING id INTO v_lesson_id;
  DELETE FROM guide_paragraphs WHERE lesson_id = v_lesson_id;
  INSERT INTO guide_paragraphs (lesson_id, content_html, sort_order) VALUES (v_lesson_id,
$html$
<p>Profession: <a href="/information/professions/Cast%20Fisher">Cast Fisher</a>. Skill: <a href="/information/skills/Casting">Casting</a>.</p>
<p>Casting splits into two phases.</p>
<h3>Throw phase</h3>
<ul>
  <li>An arrow bar determines throw distance based on where you release.</li>
  <li>Farther throws raise the chance of finding a fish but produce a longer reel-in during the catch phase, sharply increasing difficulty.</li>
  <li>Your character reels in slowly - the later in the reel a fish hooks, the easier the catch phase.</li>
  <li>Short throws can fail to find a fish at all.</li>
</ul>
<h3>Catch phase</h3>
<p>A tug-and-release mini-game. Press <strong>E</strong> to pull the fish toward you; release to let it run.</p>
<ul>
  <li>The fish tries to escape up the bar; you need to drag it down to <strong>0m</strong> to win.</li>
  <li><strong>Strength</strong> and <strong>Flexibility</strong> appear to play similar roles to Angling.</li>
  <li><strong>Line Length</strong> sets the total bar length.</li>
  <li>A circular <strong>stamina</strong> gauge limits how long you can hold E. Lose if the fish reaches the top of the bar <em>or</em> if you exhaust stamina.</li>
  <li>If the fish is already past halfway and you have full stamina, holding E from the start is usually enough to auto-win.</li>
  <li>Otherwise, watch for the same <strong>enrage</strong> mechanic - both the fish's escape speed (when not pulling) and your stamina drain (when pulling) jump significantly. You need stamina headroom to hold against an enrage or you lose fast.</li>
</ul>$html$, 0);

  INSERT INTO guide_lessons (chapter_id, title, slug, sort_order)
  VALUES (v_minigames_id, 'Fly Fishing', 'fishing-fly-fishing', 2)
  ON CONFLICT (slug) DO UPDATE
    SET chapter_id = EXCLUDED.chapter_id,
        title      = EXCLUDED.title,
        sort_order = EXCLUDED.sort_order,
        updated_at = now()
  RETURNING id INTO v_lesson_id;
  DELETE FROM guide_paragraphs WHERE lesson_id = v_lesson_id;
  INSERT INTO guide_paragraphs (lesson_id, content_html, sort_order) VALUES (v_lesson_id,
$html$
<p>Profession: <a href="/information/professions/Fly%20Fisher">Fly Fisher</a>. Skill: <a href="/information/skills/Fly%20Fishing">Fly Fishing</a>.</p>
<p>The catch portion is identical to <a href="/information/guides/fishing-angling">Angling</a>. The throw mini-game is different - details to be added once confirmed in-game.</p>$html$, 0);

  INSERT INTO guide_lessons (chapter_id, title, slug, sort_order)
  VALUES (v_minigames_id, 'Deep Ocean', 'fishing-deep-ocean', 3)
  ON CONFLICT (slug) DO UPDATE
    SET chapter_id = EXCLUDED.chapter_id,
        title      = EXCLUDED.title,
        sort_order = EXCLUDED.sort_order,
        updated_at = now()
  RETURNING id INTO v_lesson_id;
  DELETE FROM guide_paragraphs WHERE lesson_id = v_lesson_id;
  INSERT INTO guide_paragraphs (lesson_id, content_html, sort_order) VALUES (v_lesson_id,
$html$
<p>Profession: <a href="/information/professions/Deep%20Ocean%20Fisher">Deep Ocean Fisher</a>. Skill: <a href="/information/skills/Deep%20Ocean%20Fishing">Deep Ocean Fishing</a>.</p>
<p>Mechanically identical to <a href="/information/guides/fishing-casting">Casting</a>, with two requirements:</p>
<ul>
  <li>Must be performed from the <strong>seat of a water vehicle</strong>.</li>
  <li>Requires a <strong>Deep Ocean fishing rod</strong>.</li>
</ul>$html$, 0);

  INSERT INTO guide_lessons (chapter_id, title, slug, sort_order)
  VALUES (v_minigames_id, 'Baitfishing', 'fishing-baitfishing', 4)
  ON CONFLICT (slug) DO UPDATE
    SET chapter_id = EXCLUDED.chapter_id,
        title      = EXCLUDED.title,
        sort_order = EXCLUDED.sort_order,
        updated_at = now()
  RETURNING id INTO v_lesson_id;
  DELETE FROM guide_paragraphs WHERE lesson_id = v_lesson_id;
  INSERT INTO guide_paragraphs (lesson_id, content_html, sort_order) VALUES (v_lesson_id,
$html$
<p>Profession: <a href="/information/professions/Baitfisher">Baitfisher</a>. Skill: <a href="/information/skills/Baitfishing">Baitfishing</a>.</p>
<p>The <strong>Baitfishing Rod</strong> uses the <a href="/information/guides/fishing-angling">Angling</a> mini-game but with a key twist:</p>
<ul>
  <li>It needs no attachments and consumes <strong>no ammo</strong>.</li>
  <li>Each successful attempt yields 1-2 <a href="/items/materials/Baitfish">Baitfish</a>.</li>
  <li>Baitfish refine into <a href="/items/materials/Spool%20Cell">Spool Cells</a> at 1 Baitfish + 100 Universal Ammo &rarr; 100.1 Spool Cells.</li>
  <li>A more efficient Technician blueprint produces Spool Cells at a better rate but requires Transgen fruit.</li>
</ul>
<h3>Free starter trade</h3>
<p>A <strong>free Baitfishing Rod</strong> plus 10 PED of Universal Ammo can be traded for 10 PED of <a href="/items/materials/Spool%20Cell">Spool Cells</a> <strong>once</strong> at <span data-waypoint="[Calypso, 61436, 74264, 100, Lars]" data-label="Lars" class="waypoint-inline" title="Click to copy waypoint: /wp [Calypso, 61436, 74264, 100, Lars]">Lars</span> on Calypso.</p>$html$, 0);

  ---------- Chapter 4: Environmental Factors ----------

  INSERT INTO guide_lessons (chapter_id, title, slug, sort_order)
  VALUES (v_environment_id, 'Biomes', 'fishing-biomes', 0)
  ON CONFLICT (slug) DO UPDATE
    SET chapter_id = EXCLUDED.chapter_id,
        title      = EXCLUDED.title,
        sort_order = EXCLUDED.sort_order,
        updated_at = now()
  RETURNING id INTO v_lesson_id;
  DELETE FROM guide_paragraphs WHERE lesson_id = v_lesson_id;
  INSERT INTO guide_paragraphs (lesson_id, content_html, sort_order) VALUES (v_lesson_id,
$html$
<p>Four biomes only:</p>
<ul>
  <li><strong>Lake</strong></li>
  <li><strong>River</strong></li>
  <li><strong>Ocean</strong></li>
  <li><strong>Deep Ocean</strong> - effectively the Ocean biome fished with a Deep Ocean rod from a boat, typically away from the coast.</li>
</ul>
<p>Filter the <a href="/information/fishes">fish list</a> by biome to see what's available in each.</p>$html$, 0);

  INSERT INTO guide_lessons (chapter_id, title, slug, sort_order)
  VALUES (v_environment_id, 'Hot Spots', 'fishing-hot-spots', 1)
  ON CONFLICT (slug) DO UPDATE
    SET chapter_id = EXCLUDED.chapter_id,
        title      = EXCLUDED.title,
        sort_order = EXCLUDED.sort_order,
        updated_at = now()
  RETURNING id INTO v_lesson_id;
  DELETE FROM guide_paragraphs WHERE lesson_id = v_lesson_id;
  INSERT INTO guide_paragraphs (lesson_id, content_html, sort_order) VALUES (v_lesson_id,
$html$
<p>You may occasionally see splashes in the water (similar to the splash a rod makes when it hits the surface after a throw). These hot spots last roughly <strong>5-10 minutes</strong> and appear to raise hook rate while you fish inside them.</p>$html$, 0);

  INSERT INTO guide_lessons (chapter_id, title, slug, sort_order)
  VALUES (v_environment_id, 'Time, Depth, Planet & Rod', 'fishing-modifiers', 2)
  ON CONFLICT (slug) DO UPDATE
    SET chapter_id = EXCLUDED.chapter_id,
        title      = EXCLUDED.title,
        sort_order = EXCLUDED.sort_order,
        updated_at = now()
  RETURNING id INTO v_lesson_id;
  DELETE FROM guide_paragraphs WHERE lesson_id = v_lesson_id;
  INSERT INTO guide_paragraphs (lesson_id, content_html, sort_order) VALUES (v_lesson_id,
$html$
<p>Beyond biome, four extra factors gate which fish can bite:</p>
<ul>
  <li><strong>Planet</strong> - some fish are unique to specific planets.</li>
  <li><strong>Time of Day</strong> - some fish prefer or only appear during certain times.</li>
  <li><strong>Depth</strong> - some fish require a minimum lure depth to even be eligible.</li>
  <li><strong>Rod Type</strong> - some fish only bite on specific rod types.</li>
</ul>
<p>Each <a href="/information/fishes">fish info page</a> lists its specific requirements for these four factors.</p>$html$, 0);

  ---------- Chapter 5: Fish Species ----------

  INSERT INTO guide_lessons (chapter_id, title, slug, sort_order)
  VALUES (v_species_id, 'Species Overview', 'fishing-species-overview', 0)
  ON CONFLICT (slug) DO UPDATE
    SET chapter_id = EXCLUDED.chapter_id,
        title      = EXCLUDED.title,
        sort_order = EXCLUDED.sort_order,
        updated_at = now()
  RETURNING id INTO v_lesson_id;
  DELETE FROM guide_paragraphs WHERE lesson_id = v_lesson_id;
  INSERT INTO guide_paragraphs (lesson_id, content_html, sort_order) VALUES (v_lesson_id,
$html$
<p>Ten species are currently known:</p>
<ul>
  <li>Cod</li>
  <li>Carp</li>
  <li>Eel</li>
  <li>Tuna</li>
  <li>Pike</li>
  <li>Bass</li>
  <li>Catfish</li>
  <li>Salmon</li>
  <li>Sturgeon</li>
  <li>Swordfish</li>
</ul>
<p>Some of these appear to be water-specific. It is not yet confirmed whether the restriction applies to the entire species or only to certain sub-types within a species.</p>
<p>Per-fish details (biome, depth, time, planet, rod type) are listed on the individual fish pages under <a href="/information/fishes">Information &gt; Fishes</a>.</p>$html$, 0);

  ---------- Chapter 6: Material Usage ----------

  INSERT INTO guide_lessons (chapter_id, title, slug, sort_order)
  VALUES (v_materials_id, 'Refining Fish into Oil', 'fishing-refining-oil', 0)
  ON CONFLICT (slug) DO UPDATE
    SET chapter_id = EXCLUDED.chapter_id,
        title      = EXCLUDED.title,
        sort_order = EXCLUDED.sort_order,
        updated_at = now()
  RETURNING id INTO v_lesson_id;
  DELETE FROM guide_paragraphs WHERE lesson_id = v_lesson_id;
  INSERT INTO guide_paragraphs (lesson_id, content_html, sort_order) VALUES (v_lesson_id,
$html$
<ul>
  <li><a href="/items/materials/Fish%20Scrap">Fish Scrap</a> + 10 Fish &rarr; <em>&lt;Species&gt;</em> Fish Oil. The required Fish Scrap quantity varies by species.</li>
  <li><strong>Tip:</strong> refining a species-specific oil a second time yields generic <a href="/items/materials/Fish%20Oil">Fish Oil</a>. For example, <a href="/items/materials/Cod%20Fish%20Oil">Cod Fish Oil</a> &rarr; Fish Oil.</li>
</ul>$html$, 0);

  INSERT INTO guide_lessons (chapter_id, title, slug, sort_order)
  VALUES (v_materials_id, 'Port Atlantis AI Dailies', 'fishing-ai-dailies', 1)
  ON CONFLICT (slug) DO UPDATE
    SET chapter_id = EXCLUDED.chapter_id,
        title      = EXCLUDED.title,
        sort_order = EXCLUDED.sort_order,
        updated_at = now()
  RETURNING id INTO v_lesson_id;
  DELETE FROM guide_paragraphs WHERE lesson_id = v_lesson_id;
  INSERT INTO guide_paragraphs (lesson_id, content_html, sort_order) VALUES (v_lesson_id,
$html$
<p>Two AI dailies in Port Atlantis can request caught fish, located at <span data-waypoint="[Calypso, 61426, 74267, 100, AI Dailies]" data-label="AI Dailies" class="waypoint-inline" title="Click to copy waypoint: /wp [Calypso, 61426, 74267, 100, AI Dailies]">AI Dailies</span>. Rewards include a small amount of <a href="/items/materials/Spool%20Cell">Spool Cells</a> and Fishing/Cooking-related <strong>blueprint clicks</strong>.</p>$html$, 0);

  -- Drop the Quick Reference lesson if a prior run of this migration created it.
  -- Paragraphs cascade via FK ON DELETE CASCADE.
  DELETE FROM guide_lessons WHERE slug = 'fishing-quick-reference';

END
$mig$;

COMMIT;
