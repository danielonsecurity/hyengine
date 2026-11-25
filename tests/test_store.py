"""DefinitionStore: layered definition files (e.g. global + user), written back in place."""

import os
from datetime import datetime

import pytest

from hyengine import Code, Definition, DefinitionStore


@pytest.fixture
def layers(tmp_path):
    global_dir, user_dir = tmp_path / "global", tmp_path / "user"
    global_dir.mkdir()
    user_dir.mkdir()
    (global_dir / "default.hy").write_text(
        ";; shipped defaults\n\n(def-p A (v 1))\n\n(def-p B (v 2))\n"
    )
    (user_dir / "default.hy").write_text("(def-p B (v 20))\n")
    (user_dir / "work.hy").write_text(";; my work items\n\n(def-p C (v 3))\n\n(def-p D (v 4))\n")
    return global_dir, user_dir


def store_for(layers, **kw):
    s = DefinitionStore(list(layers), **kw)
    s.load()
    return s


def values(store):
    return {name: d.props["v"] for name, d in store.items()}


class TestReading:
    def test_higher_layers_override_lower_ones(self, layers):
        assert values(store_for(layers)) == {"A": 1, "B": 20, "C": 3, "D": 4}

    def test_origin_is_tracked(self, layers):
        s = store_for(layers)
        assert s.origin("A") == (layers[0] / "default.hy", 0)
        assert s.origin("B") == (layers[1] / "default.hy", 1)
        assert s.origin("C") == (layers[1] / "work.hy", 1)

    def test_names_by_file(self, layers):
        assert store_for(layers).names_in("work.hy") == ["C", "D"]

    def test_missing_layer_directories_are_fine(self, tmp_path):
        s = store_for([tmp_path / "nope", tmp_path / "also-nope"])
        assert list(s.items()) == []


class TestWriting:
    def test_put_updates_item_in_its_own_file(self, layers):
        s = store_for(layers)
        s.put(Definition(head="def-p", name="C", props={"v": 30}))
        s.save()
        assert values(store_for(layers))["C"] == 30
        assert "(def-p C\n  (v 30)\n)" in (layers[1] / "work.hy").read_text()

    def test_untouched_files_are_not_rewritten(self, layers):
        s = store_for(layers)
        before = (layers[1] / "default.hy").read_text()
        s.put(Definition(head="def-p", name="C", props={"v": 30}))
        s.save()
        assert (layers[1] / "default.hy").read_text() == before

    def test_header_comments_and_order_are_kept(self, layers):
        s = store_for(layers)
        s.put(Definition(head="def-p", name="C", props={"v": 30}))
        s.save()
        text = (layers[1] / "work.hy").read_text()
        assert text.startswith(";; my work items\n")
        assert text.index("def-p C") < text.index("def-p D")

    def test_new_items_go_to_the_default_file_or_a_given_file(self, layers):
        s = store_for(layers)
        s.put(Definition(head="def-p", name="E", props={"v": 5}))
        s.put(Definition(head="def-p", name="F", props={"v": 6}), file="errands.hy")
        s.save()
        fresh = store_for(layers)
        assert fresh.origin("E") == (layers[1] / "default.hy", 1)
        assert fresh.origin("F") == (layers[1] / "errands.hy", 1)

    def test_overriding_a_global_item_writes_it_to_the_user_layer(self, layers):
        s = store_for(layers)
        global_text = (layers[0] / "default.hy").read_text()
        s.put(Definition(head="def-p", name="A", props={"v": 100}))
        s.save()
        assert (layers[0] / "default.hy").read_text() == global_text
        assert values(store_for(layers))["A"] == 100

    def test_global_items_are_never_copied_into_user_files(self, layers):
        s = store_for(layers)
        s.put(Definition(head="def-p", name="E", props={"v": 5}))
        s.save()
        assert "def-p A" not in (layers[1] / "default.hy").read_text()

    def test_remove_and_delete_emptied_file(self, layers):
        s = store_for(layers)
        s.remove("C")
        s.remove("D")
        s.save()
        assert not (layers[1] / "work.hy").exists()
        assert "C" not in values(store_for(layers))

    def test_removing_a_user_override_reveals_the_global_item(self, layers):
        s = store_for(layers)
        assert s.remove("B")
        s.save()
        assert values(store_for(layers))["B"] == 2

    def test_global_only_items_cannot_be_removed(self, layers):
        s = store_for(layers)
        assert s.remove("A") is False
        assert s.get("A") is not None

    def test_move_to_another_file(self, layers):
        s = store_for(layers)
        s.put(s.get("C"), file="archive.hy")
        s.save()
        fresh = store_for(layers)
        assert fresh.origin("C") == (layers[1] / "archive.hy", 1)
        assert fresh.names_in("work.hy") == ["D"]

    def test_code_and_datetimes_round_trip_through_save(self, layers):
        s = store_for(layers)
        when = datetime(2025, 1, 2, 3, 4, 5, 6)
        s.put(Definition(head="def-p", name="G", props={"v": when, "hook": Code("(setv x 1)")}))
        s.save()
        g = store_for(layers).get("G")
        assert g.props == {"v": when, "hook": Code("(setv x 1)")}


class TestCache:
    def test_cached_load_equals_fresh_load(self, layers, tmp_path):
        cache = tmp_path / "cache"
        fresh = {n: d for n, d in store_for(layers).items()}
        store_for(layers, cache_dir=cache)  # populate
        assert any(cache.iterdir())
        cached = {n: d for n, d in store_for(layers, cache_dir=cache).items()}
        assert cached == fresh

    def test_cache_is_not_used_after_a_file_changes(self, layers, tmp_path):
        cache = tmp_path / "cache"
        store_for(layers, cache_dir=cache)
        path = layers[1] / "work.hy"
        path.write_text("(def-p C (v 99))\n")
        os.utime(path, ns=(path.stat().st_atime_ns, path.stat().st_mtime_ns + 1_000_000))
        assert values(store_for(layers, cache_dir=cache))["C"] == 99

    def test_corrupt_cache_falls_back_to_parsing(self, layers, tmp_path):
        cache = tmp_path / "cache"
        store_for(layers, cache_dir=cache)
        for f in cache.iterdir():
            f.write_bytes(b"garbage")
        assert values(store_for(layers, cache_dir=cache))["C"] == 3


def test_code_values_store_keeps_hand_written_code_exactly(tmp_path):
    trait_dir = tmp_path / "traits"
    trait_dir.mkdir()
    source = (
        "(def-trait counter\n"
        "  (actions {:bump (fn [self]\n"
        "                    ;; add one\n"
        "                    (setv self.count (+ self.count 1)))}))\n"
    )
    (trait_dir / "counter.hy").write_text(source)
    store = DefinitionStore([trait_dir], code_values=True).load()
    action = store.get("counter").props["actions"]["bump"]
    assert action.source == "(fn [self]\n                    ;; add one\n                    (setv self.count (+ self.count 1)))"
    store.put(store.get("counter"))
    store.save()
    again = DefinitionStore([trait_dir], code_values=True).load().get("counter")
    assert again.props["actions"]["bump"] == action


class TestCustomKeys:
    """key=(definition, file) -> identity, e.g. (category, name) when a name may repeat across files."""

    @pytest.fixture
    def by_file(self, tmp_path):
        g, u = tmp_path / "g", tmp_path / "u"
        g.mkdir(); u.mkdir()
        (g / "work.hy").write_text('(def-t "Sleep" (v 1))\n')
        (u / "work.hy").write_text('(def-t "Sleep" (v 10))\n')
        (u / "home.hy").write_text('(def-t "Sleep" (v 2))\n')
        return g, u

    @staticmethod
    def key(definition, path):
        return (path.stem, definition.name)

    def test_same_name_in_different_files_are_different_items(self, by_file):
        s = DefinitionStore(list(by_file), key=self.key).load()
        assert {k: d.props["v"] for k, d in s.items()} == {("work", "Sleep"): 10, ("home", "Sleep"): 2}

    def test_put_and_remove_by_key(self, by_file):
        s = DefinitionStore(list(by_file), key=self.key).load()
        s.put(Definition(head="def-t", name="Sleep", props={"v": 3}), file="errands.hy")
        assert s.remove(("home", "Sleep"))
        s.save()
        fresh = DefinitionStore(list(by_file), key=self.key).load()
        assert {k: d.props["v"] for k, d in fresh.items()} == {("work", "Sleep"): 10, ("errands", "Sleep"): 3}
        assert not (by_file[1] / "home.hy").exists()

    def test_names_in_returns_keys(self, by_file):
        s = DefinitionStore(list(by_file), key=self.key).load()
        assert s.names_in("home.hy") == [("home", "Sleep")]


def test_on_error_skips_broken_files_and_reports_them(tmp_path):
    layer = tmp_path / "items"
    layer.mkdir()
    (layer / "good.hy").write_text("(def-p A (v 1))\n")
    (layer / "bad.hy").write_text("(def-p B (v (call-something)))\n")
    errors = []
    store = DefinitionStore([layer], on_error=lambda path, exc: errors.append(path.name)).load()
    assert store.names() == ["A"]
    assert errors == ["bad.hy"]


def test_without_on_error_broken_files_raise(tmp_path):
    from hyengine.errors import HyDataError

    layer = tmp_path / "items"
    layer.mkdir()
    (layer / "bad.hy").write_text("(def-p B (v (call-something)))\n")
    with pytest.raises(HyDataError):
        DefinitionStore([layer]).load()


class TestConcurrentWriters:
    """Two processes (e.g. a web API and a scheduler) using the same files."""

    @staticmethod
    def touch_later(path):
        stat = path.stat()
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 5_000_000))

    def test_refresh_reloads_files_changed_by_someone_else(self, layers):
        mine = store_for(layers)
        other = store_for(layers)
        other.put(Definition(head="def-p", name="C", props={"v": 33}))
        other.save()
        self.touch_later(layers[1] / "work.hy")
        assert mine.changed_files() == [layers[1] / "work.hy"]
        assert mine.refresh() is True
        assert mine.get("C").props["v"] == 33
        assert mine.refresh() is False

    def test_refresh_sees_new_and_deleted_files(self, layers):
        mine = store_for(layers)
        (layers[1] / "extra.hy").write_text("(def-p X (v 9))\n")
        (layers[1] / "work.hy").unlink()
        assert mine.refresh() is True
        assert mine.get("X").props["v"] == 9 and mine.get("C") is None

    def test_saving_over_a_file_changed_on_disk_is_a_conflict(self, layers):
        from hyengine.errors import StoreConflict

        mine = store_for(layers)
        (layers[1] / "work.hy").write_text("(def-p C (v 300))\n(def-p D (v 4))\n")
        self.touch_later(layers[1] / "work.hy")
        mine.put(Definition(head="def-p", name="C", props={"v": 30}))
        with pytest.raises(StoreConflict, match="work.hy"):
            mine.save()
        assert "(v 300)" in (layers[1] / "work.hy").read_text()  # the other writer's change survives

    def test_own_saves_are_not_conflicts(self, layers):
        mine = store_for(layers)
        for value in (1, 2, 3):
            mine.put(Definition(head="def-p", name="C", props={"v": value}))
            mine.save()
        assert store_for(layers).get("C").props["v"] == 3
        assert mine.changed_files() == []
