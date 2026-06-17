#!/usr/bin/env python3
"""
Startup Validation CLI for Aviation Girl V4 Discord Bot

Command-line interface for running startup validation checks.
"""

import asyncio
import argparse
import sys
import json
import logging
from pathlib import Path

from .config_manager import ConfigManager
from .startup_validator import StartupValidator, ValidationStatus


class StartupCLI:
    """Command-line interface for startup validation"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def create_parser(self) -> argparse.ArgumentParser:
        """Create command-line argument parser"""
        parser = argparse.ArgumentParser(
            description="Aviation Girl V4 Startup Validation",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  %(prog)s validate                    # Run all validation checks
  %(prog)s validate --api-only         # Run only API connection checks
  %(prog)s validate --config config.json  # Use specific config file
  %(prog)s validate --output report.json  # Save report to file
  %(prog)s validate --verbose          # Enable verbose output
            """
        )
        
        parser.add_argument(
            'command',
            choices=['validate'],
            help='Command to run'
        )
        
        parser.add_argument(
            '--config', '-c',
            type=str,
            help='Configuration file path'
        )
        
        parser.add_argument(
            '--api-only',
            action='store_true',
            help='Run only API connection validation checks'
        )
        
        parser.add_argument(
            '--output', '-o',
            type=str,
            help='Output file for validation report (JSON format)'
        )
        
        parser.add_argument(
            '--verbose', '-v',
            action='store_true',
            help='Enable verbose output'
        )
        
        parser.add_argument(
            '--quiet', '-q',
            action='store_true',
            help='Suppress all output except errors'
        )
        
        return parser
    
    async def run(self, args=None) -> int:
        """Run the CLI with given arguments"""
        parser = self.create_parser()
        parsed_args = parser.parse_args(args)
        
        # Setup logging
        if parsed_args.quiet:
            log_level = logging.ERROR
        elif parsed_args.verbose:
            log_level = logging.DEBUG
        else:
            log_level = logging.INFO
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        try:
            if parsed_args.command == 'validate':
                return await self._validate_command(parsed_args)
            else:
                parser.print_help()
                return 0
                
        except Exception as e:
            if not parsed_args.quiet:
                print(f"  Error: {e}")
            self.logger.error(f"CLI error: {e}")
            return 1
    
    async def _validate_command(self, args) -> int:
        """Handle validate command"""
        if not args.quiet:
            print("  Loading configuration...")
        
        # Load configuration
        config_manager = ConfigManager(config_file=args.config)
        try:
            config = await config_manager.load_configuration()
        except Exception as e:
            if not args.quiet:
                print(f"  Failed to load configuration: {e}")
            return 1
        
        if not args.quiet:
            print("  Configuration loaded successfully")
        
        # Create validator
        validator = StartupValidator(config)
        
        if not args.quiet:
            print("  Running startup validation...")
        
        # Run validation
        if args.api_only:
            # Run only API checks
            api_results = await validator.validate_api_connections_only()
            
            # Create a simplified report for API-only validation
            passed = sum(1 for r in api_results.values() if r.status == ValidationStatus.PASSED)
            failed = sum(1 for r in api_results.values() if r.status == ValidationStatus.FAILED)
            skipped = sum(1 for r in api_results.values() if r.status == ValidationStatus.SKIPPED)
            
            if not args.quiet:
                print(f"\n   API Validation Results:")
                print(f"  Total APIs: {len(api_results)}")
                print(f"  Passed: {passed}")
                print(f"  Failed: {failed}")
                print(f"  Skipped: {skipped}")
                
                print(f"\n📋 Detailed Results:")
                for api_name, result in api_results.items():
                    status_icon = self._get_status_icon(result.status)
                    print(f"  {status_icon} {api_name}: {result.message}")
            
            # Save report if requested
            if args.output:
                report_data = {
                    "api_validation": True,
                    "results": {
                        name: {
                            "status": result.status.value,
                            "message": result.message,
                            "details": result.details,
                            "error": result.error
                        }
                        for name, result in api_results.items()
                    }
                }
                
                with open(args.output, 'w') as f:
                    json.dump(report_data, f, indent=2)
                
                if not args.quiet:
                    print(f"📄 Report saved to: {args.output}")
            
            # Return appropriate exit code
            return 0 if failed == 0 else 1
            
        else:
            # Run full validation
            report = await validator.validate_startup()
            
            if not args.quiet:
                print(f"\n   Validation Summary:")
                print(f"  Overall Status: {self._get_status_icon(report.overall_status)} {report.overall_status.value.upper()}")
                print(f"  Total Checks: {report.total_checks}")
                print(f"  Passed: {report.passed_checks}")
                print(f"  Failed: {report.failed_checks}")
                print(f"  Warnings: {report.warning_checks}")
                print(f"  Skipped: {report.skipped_checks}")
                print(f"  Duration: {report.total_duration_ms:.1f}ms")
                
                # Show system info
                if report.system_info and args.verbose:
                    print(f"\n💻 System Information:")
                    for key, value in report.system_info.items():
                        print(f"  {key}: {value}")
                
                # Show detailed results
                print(f"\n📋 Detailed Results:")
                for result in report.validation_results:
                    status_icon = self._get_status_icon(result.status)
                    duration_str = f" ({result.duration_ms:.1f}ms)" if result.duration_ms else ""
                    print(f"  {status_icon} {result.name}: {result.message}{duration_str}")
                    
                    if args.verbose and result.details:
                        for key, value in result.details.items():
                            print(f"    {key}: {value}")
                    
                    if result.error and args.verbose:
                        print(f"    Error: {result.error}")
            
            # Save report if requested
            if args.output:
                report_json = validator.generate_report_json(report)
                with open(args.output, 'w') as f:
                    f.write(report_json)
                
                if not args.quiet:
                    print(f"📄 Report saved to: {args.output}")
            
            # Return appropriate exit code
            if report.overall_status == ValidationStatus.FAILED:
                return 1
            elif report.overall_status == ValidationStatus.WARNING:
                return 0  # Warnings don't cause failure
            else:
                return 0
    
    def _get_status_icon(self, status: ValidationStatus) -> str:
        """Get icon for validation status"""
        icons = {
            ValidationStatus.PASSED: " ",
            ValidationStatus.FAILED: " ",
            ValidationStatus.WARNING: "⚠️",
            ValidationStatus.SKIPPED: "⏭️",
            ValidationStatus.PENDING: "⏳"
        }
        return icons.get(status, "❓")


async def main():
    """Main entry point for CLI"""
    cli = StartupCLI()
    return await cli.run()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))