"""Event bus contracts.

Defines the interfaces for publishing, subscribing to, and
managing domain events. Implementations (Redis Streams, Kafka,
in-memory) live in the infrastructure layer and implement these
contracts.
"""
