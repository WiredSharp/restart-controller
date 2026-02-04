"""Tests for DependencyTree."""

from restart_controller.dependency_tree import DependencyTree


class TestAdd:
    def test_single_parent_child(self):
        tree = DependencyTree()
        tree.add("parent", ["child"])
        assert tree.get_children("parent") == {"child"}

    def test_multiple_children(self):
        tree = DependencyTree()
        tree.add("a", ["b", "c", "d"])
        assert tree.get_children("a") == {"b", "c", "d"}

    def test_chain(self):
        tree = DependencyTree()
        tree.add("a", ["b"])
        tree.add("b", ["c"])
        assert tree.get_children("a") == {"b"}
        assert tree.get_children("b") == {"c"}

    def test_add_updates_descendants(self):
        tree = DependencyTree()
        tree.add("a", ["b"])
        assert tree.get_descendants("a") == frozenset({"b"})
        tree.add("b", ["c"])
        assert tree.get_descendants("a") == frozenset({"b", "c"})

    def test_duplicate_children_ignored(self):
        tree = DependencyTree()
        tree.add("a", ["b", "b", "c"])
        assert tree.get_children("a") == {"b", "c"}
        tree.add("a", ["c", "d"])
        assert tree.get_children("a") == {"b", "c", "d"}

    def test_no_children(self):
        tree = DependencyTree()
        assert tree.get_children("anything") == set()


class TestGetDescendants:
    def test_leaf_node(self):
        tree = DependencyTree()
        tree.add("a", ["b"])
        assert tree.get_descendants("b") == frozenset()

    def test_direct_children(self):
        tree = DependencyTree()
        tree.add("a", ["b", "c"])
        assert tree.get_descendants("a") == frozenset({"b", "c"})

    def test_transitive_descendants(self):
        tree = DependencyTree()
        tree.add("a", ["b"])
        tree.add("b", ["c"])
        tree.add("c", ["d"])
        assert tree.get_descendants("a") == frozenset({"b", "c", "d"})

    def test_branching_tree(self):
        #     a
        #    / \
        #   b   c
        #  /
        # d
        tree = DependencyTree()
        tree.add("a", ["b", "c"])
        tree.add("b", ["d"])
        assert tree.get_descendants("a") == frozenset({"b", "c", "d"})

    def test_subtree(self):
        tree = DependencyTree()
        tree.add("a", ["b", "c"])
        tree.add("b", ["d"])
        assert tree.get_descendants("b") == frozenset({"d"})

    def test_unknown_node(self):
        tree = DependencyTree()
        assert tree.get_descendants("unknown") == frozenset()


class TestComputeRestartSet:
    def test_single_trigger_restarts_children(self):
        tree = DependencyTree()
        tree.add("a", ["b", "c"])
        assert tree.compute_restart_set({"a"}) == {"b", "c"}

    def test_trigger_restarts_transitive_descendants(self):
        tree = DependencyTree()
        tree.add("a", ["b"])
        tree.add("b", ["c"])
        assert tree.compute_restart_set({"a"}) == {"b", "c"}

    def test_dedup_when_ancestor_also_triggers(self):
        # a -> b -> c
        # If both a and b trigger, c should appear only once
        tree = DependencyTree()
        tree.add("a", ["b"])
        tree.add("b", ["c"])
        result = tree.compute_restart_set({"a", "b"})
        # b is a trigger so it's excluded; c is a descendant of both but only counted once
        assert result == {"c"}

    def test_leaf_trigger_no_restart(self):
        tree = DependencyTree()
        tree.add("a", ["b"])
        tree.add("b", ["c"])
        assert tree.compute_restart_set({"c"}) == set()

    def test_independent_subtrees(self):
        #  a      x
        #  |      |
        #  b      y
        tree = DependencyTree()
        tree.add("a", ["b"])
        tree.add("x", ["y"])
        assert tree.compute_restart_set({"a"}) == {"b"}

    def test_multiple_independent_triggers(self):
        tree = DependencyTree()
        tree.add("a", ["b"])
        tree.add("x", ["y"])
        assert tree.compute_restart_set({"a", "x"}) == {"b", "y"}

    def test_empty_triggers(self):
        tree = DependencyTree()
        tree.add("a", ["b"])
        assert tree.compute_restart_set(set()) == set()
