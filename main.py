#!/usr/bin/env python3
"""
StreamToy - Main Entry Point

A modular game/app framework for StreamDock devices.
Supports both physical hardware and web-based emulation.
"""

import argparse
import logging
import os
import sys
from stream_toy.runtime import StreamToyRuntime


def setup_logging(level: str) -> None:
    """
    Configure logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
    """
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=log_format,
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='StreamToy - Interactive game framework for StreamDock devices',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Run with both hardware and web emulator
  %(prog)s --no-hardware            # Web emulator only
  %(prog)s --no-web                 # Hardware only
  %(prog)s --web-port 8080          # Use custom web port
  %(prog)s --log-level DEBUG        # Enable debug logging
        """
    )

    parser.add_argument(
        '--no-hardware',
        action='store_true',
        help='Disable real StreamDock hardware device'
    )

    parser.add_argument(
        '--no-web',
        action='store_true',
        help='Disable web browser emulator'
    )

    parser.add_argument(
        '--web-port',
        type=int,
        default=5000,
        help='Web emulator port (default: 5000)'
    )

    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level (default: INFO)'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    # Validate arguments
    if args.no_hardware and args.no_web:
        logger.error("Cannot disable both hardware and web emulator!")
        sys.exit(1)

    # Print banner
    print("=" * 60)
    print("  StreamToy - Interactive Game Framework")
    print("  Version 1.0.0")
    print("=" * 60)
    print()

    if not args.no_hardware:
        print("✓ Hardware device: ENABLED")
    else:
        print("✗ Hardware device: DISABLED")

    if not args.no_web:
        print(f"✓ Web emulator: ENABLED (http://0.0.0.0:{args.web_port})")
    else:
        print("✗ Web emulator: DISABLED")

    print()
    print("Press Ctrl+C to exit")
    print("=" * 60)
    print()

    # Create and start runtime
    try:
        runtime = StreamToyRuntime(
            enable_hardware=not args.no_hardware,
            enable_web=not args.no_web,
            web_port=args.web_port
        )

        logger.info("Starting StreamToy Runtime...")
        runtime.start()

    except KeyboardInterrupt:
        print("\n\nShutdown requested by user")
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\nERROR: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
