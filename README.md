# Kubernetes Pods restart controller

The objective is to have a solution to enforce pod restart synchronization when pods have dependencies between each other.

I need to synchronise restart of pods managed by deployment.
A given pods may have at most one parent and zero or more childs.
If it restarts, its childs must be restarted too.
We must ensure not to restart a pod several times if several of its parents (by transitivity) restarts.
I already have init container to enforce child pod to wait for their parents.
Annotations are a good way to store information about last triggered restart.
restart should be managed through deployment.