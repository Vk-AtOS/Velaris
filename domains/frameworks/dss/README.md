# frameworks/dss — Distributed Storage System

Distributed storage and data management framework. DSS agents handle clustering, replication, failover, scaling, and load balancing for all persistent data across the BOS.

| Agent | Description |
|-------|-------------|
| DSS_CLUSTER_MANAGER | Manages storage cluster topology — node membership and health |
| DSS_FAILOVER | Handles automatic failover when storage nodes fail |
| DSS_LOAD_BALANCER | Balances read/write load across storage nodes |
| DSS_MONITOR | Monitors storage health, capacity, and performance continuously |
| DSS_REPLICATION | Manages data replication across nodes for durability |
| DSS_SCALER | Auto-scales storage capacity based on usage trends |
