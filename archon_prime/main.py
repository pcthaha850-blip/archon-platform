#!/usr/bin/env python3
# ARCHON_FEAT: main-entry-001
"""
ARCHON PRIME - Main Entry Point
===============================

Production trading platform entry point.

Usage:
    python -m archon_prime.main --config config/paper.yaml
    python -m archon_prime.main --config config/live.yaml --mode live

Author: ARCHON Development Team
Version: 2.0.0
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from archon_prime.core.orchestrator import Orchestrator
from archon_prime.core.config_manager import ConfigManager


def setup_logging(level: str = "INFO") -> None:
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="ARCHON PRIME - Production Trading Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-c", "--config",
        type=str,
        default="config/paper.yaml",
        help="Path to configuration file (default: config/paper.yaml)",
    )

    parser.add_argument(
        "-m", "--mode",
        type=str,
        choices=["paper", "live"],
        default=None,
        help="Trading mode (overrides config)",
    )

    parser.add_argument(
        "-p", "--plugins",
        type=str,
        nargs="+",
        default=["archon_prime/plugins"],
        help="Plugin directories to load",
    )

    parser.add_argument(
        "-l", "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config and exit without trading",
    )

    return parser.parse_args()


async def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger("ARCHON_MAIN")

    logger.info("=" * 60)
    logger.info("ARCHON PRIME - Production Trading Platform")
    logger.info("=" * 60)

    # Check config exists
    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"Configuration file not found: {config_path}")
        return 1

    # Dry run - validate only
    if args.dry_run:
        logger.info("Dry run mode - validating configuration...")
        config_manager = ConfigManager(config_path)
        errors = config_manager.validate()

        if errors:
            for error in errors:
                logger.error(f"Validation error: {error}")
            return 1

        logger.info("Configuration valid!")
        logger.info(f"Mode: {config_manager.config.mode}")
        logger.info(f"Symbols: {config_manager.trading.symbols}")
        logger.info(f"Max positions: {config_manager.trading.max_positions}")
        return 0

    # Create orchestrator
    orchestrator = Orchestrator()

    # Start
    logger.info(f"Loading configuration: {config_path}")

    plugin_dirs = [Path(p) for p in args.plugins]

    if not await orchestrator.start(
        config_path=str(config_path),
        plugin_dirs=[str(p) for p in plugin_dirs if p.exists()],
    ):
        logger.error("Failed to start orchestrator")
        return 1

    # Override mode if specified
    if args.mode:
        orchestrator.config.set("mode", args.mode)
        logger.info(f"Mode overridden to: {args.mode}")

    # Run
    logger.info("ARCHON PRIME running. Press Ctrl+C to stop.")

    try:
        await orchestrator.run_forever()
    except KeyboardInterrupt:
        logger.info("Shutdown requested...")
    finally:
        await orchestrator.shutdown()

    logger.info("ARCHON PRIME shutdown complete")
    return 0


def run() -> None:
    """Synchronous entry point."""
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run()
