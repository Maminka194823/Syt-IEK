#!/usr/bin/env python3
"""
Configuration CLI Utility for Aviation Girl V4 Discord Bot

Command-line interface for configuration management, validation, and testing.
"""

import asyncio
import argparse
import json
import sys
import logging
from pathlib import Path
from typing import Optional

from .config_manager import ConfigManager, ConfigurationError
from .config_validator import ConfigValidator


class ConfigCLI:
    """Command-line interface for configuration management"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.validator = ConfigValidator()
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def create_parser(self) -> argparse.ArgumentParser:
        """Create command-line argument parser"""
        parser = argparse.ArgumentParser(
            description="Aviation Girl V4 Configuration Management",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  %(prog)s validate                          # Validate current configuration
  %(prog)s validate --config config.json    # Validate specific config file
  %(prog)s test-apis                         # Test API connections
  %(prog)s export --format yaml             # Export config to YAML
  %(prog)s summary                           # Show configuration summary
            """
        )
        
        parser.add_argument(
            '--config', '-c',
            type=str,
            help='Configuration file path'
        )
        
        parser.add_argument(
            '--verbose', '-v',
            action='store_true',
            help='Enable verbose output'
        )
        
        subparsers = parser.add_subparsers(dest='command', help='Available commands')
        
        # Validate command
        validate_parser = subparsers.add_parser(
            'validate',
            help='Validate configuration'
        )
        validate_parser.add_argument(
            '--show-warnings',
            action='store_true',
            help='Show warnings in addition to errors'
        )
        validate_parser.add_argument(
            '--show-suggestions',
            action='store_true',
            help='Show suggestions for improvements'
        )
        
        # Test APIs command
        test_parser = subparsers.add_parser(
            'test-apis',
            help='Test external API connections'
        )
        test_parser.add_argument(
            '--timeout',
            type=int,
            default=30,
            help='Connection timeout in seconds'
        )
        
        # Export command
        export_parser = subparsers.add_parser(
            'export',
            help='Export configuration to file'
        )
        export_parser.add_argument(
            '--output', '-o',
            type=str,
            required=True,
            help='Output file path'
        )
        export_parser.add_argument(
            '--format', '-f',
            choices=['json', 'yaml'],
            default='json',
            help='Output format'
        )
        
        # Summary command
        subparsers.add_parser(
            'summary',
            help='Show configuration summary'
        )
        
        # Check command
        check_parser = subparsers.add_parser(
            'check',
            help='Check configuration and system readiness'
        )
        check_parser.add_argument(
            '--fix-paths',
            action='store_true',
            help='Attempt to create missing directories'
        )
        
        return parser
    
    async def run(self, args: Optional[list] = None) -> int:
        """Run the CLI with given arguments"""
        parser = self.create_parser()
        parsed_args = parser.parse_args(args)
        
        if parsed_args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
        
        # Set config file if provided
        if parsed_args.config:
            self.config_manager.config_file = parsed_args.config
        
        try:
            if parsed_args.command == 'validate':
                return await self._validate_command(parsed_args)
            elif parsed_args.command == 'test-apis':
                return await self._test_apis_command(parsed_args)
            elif parsed_args.command == 'export':
                return await self._export_command(parsed_args)
            elif parsed_args.command == 'summary':
                return await self._summary_command(parsed_args)
            elif parsed_args.command == 'check':
                return await self._check_command(parsed_args)
            else:
                parser.print_help()
                return 0
                
        except ConfigurationError as e:
            self.logger.error(f"Configuration error: {e}")
            return 1
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            if parsed_args.verbose:
                import traceback
                traceback.print_exc()
            return 1
    
    async def _validate_command(self, args) -> int:
        """Handle validate command"""
        print("  Loading and validating configuration...")
        
        try:
            config = await self.config_manager.load_configuration()
            print("  Configuration loaded successfully")
            
            print("\n  Running comprehensive validation...")
            result = await self.validator.validate_configuration(config)
            
            if result.is_valid:
                print("  Configuration validation passed!")
            else:
                print("  Configuration validation failed!")
                print(f"\n🚨 Errors ({len(result.errors)}):")
                for i, error in enumerate(result.errors, 1):
                    print(f"  {i}. {error}")
            
            if args.show_warnings and result.warnings:
                print(f"\n⚠️  Warnings ({len(result.warnings)}):")
                for i, warning in enumerate(result.warnings, 1):
                    print(f"  {i}. {warning}")
            
            if args.show_suggestions and result.suggestions:
                print(f"\n💡 Suggestions ({len(result.suggestions)}):")
                for i, suggestion in enumerate(result.suggestions, 1):
                    print(f"  {i}. {suggestion}")
            
            return 0 if result.is_valid else 1
            
        except Exception as e:
            print(f"  Validation failed: {e}")
            return 1
    
    async def _test_apis_command(self, args) -> int:
        """Handle test-apis command"""
        print("  Loading configuration...")
        
        try:
            config = await self.config_manager.load_configuration()
            print("  Configuration loaded")
            
            print(f"\n🌐 Testing API connections (timeout: {args.timeout}s)...")
            results = await self.validator.test_api_connections(config)
            
            print(f"\n   API Connection Results:")
            print(f"  Total APIs: {results['total_apis']}")
            print(f"  Successful: {results['successful']}")
            print(f"  Failed: {results['failed']}")
            
            if results['apis']:
                print(f"\n📋 Detailed Results:")
                for api_name, api_result in results['apis'].items():
                    status_icon = " " if api_result['status'] == 'success' else " "
                    print(f"  {status_icon} {api_name}: {api_result['message']}")
                    
                    if api_result['status'] == 'success' and 'response_time' in api_result:
                        print(f"    Response time: {api_result['response_time']}ms")
                    elif api_result['status'] == 'failed' and 'error' in api_result:
                        print(f"    Error: {api_result['error']}")
            
            return 0 if results['failed'] == 0 else 1
            
        except Exception as e:
            print(f"  API testing failed: {e}")
            return 1
    
    async def _export_command(self, args) -> int:
        """Handle export command"""
        print("  Loading configuration...")
        
        try:
            config = await self.config_manager.load_configuration()
            print("  Configuration loaded")
            
            print(f"\n📤 Exporting configuration to {args.output} ({args.format})...")
            self.config_manager.export_config(args.output, args.format)
            print("  Configuration exported successfully")
            
            return 0
            
        except Exception as e:
            print(f"  Export failed: {e}")
            return 1
    
    async def _summary_command(self, args) -> int:
        """Handle summary command"""
        print("  Loading configuration...")
        
        try:
            config = await self.config_manager.load_configuration()
            summary = self.config_manager.get_config_summary()
            
            print("\n📋 Configuration Summary:")
            print(f"  Status: {summary['status']}")
            print(f"  Environment: {summary['environment']}")
            print(f"  Debug Mode: {summary['debug_mode']}")
            print(f"  Discord Prefix: {summary['discord_prefix']}")
            print(f"  AI Model: {summary['ai_model']}")
            print(f"  Memory Enabled: {summary['memory_enabled']}")
            print(f"  RAG Enabled: {summary['rag_enabled']}")
            print(f"  Security Enabled: {summary['security_enabled']}")
            print(f"  Metrics Enabled: {summary['metrics_enabled']}")
            print(f"  Log Level: {summary['log_level']}")
            
            if summary['validation_errors'] > 0:
                print(f"  ⚠️  Validation Errors: {summary['validation_errors']}")
            else:
                print("    No validation errors")
            
            return 0
            
        except Exception as e:
            print(f"  Summary failed: {e}")
            return 1
    
    async def _check_command(self, args) -> int:
        """Handle check command"""
        print("  Checking system readiness...")
        
        try:
            config = await self.config_manager.load_configuration()
            print("  Configuration loaded")
            
            # Run validation
            result = await self.validator.validate_configuration(config)
            
            # Check system components
            print("\n  Checking system components...")
            
            # Check required directories
            directories_to_check = [
                ("Vector DB", config.knowledge.vector_db_path),
                ("Logs", config.monitoring.log_file_path),
                ("Encryption Keys", config.security.encryption_key_path),
                ("Audit Logs", config.security.audit_log_path),
            ]
            
            missing_dirs = []
            for name, path in directories_to_check:
                if path:
                    dir_path = Path(path).parent
                    if not dir_path.exists():
                        missing_dirs.append((name, str(dir_path)))
                        print(f"    {name} directory missing: {dir_path}")
                    else:
                        print(f"    {name} directory exists: {dir_path}")
            
            # Fix missing directories if requested
            if args.fix_paths and missing_dirs:
                print(f"\n🔧 Creating missing directories...")
                for name, dir_path in missing_dirs:
                    try:
                        Path(dir_path).mkdir(parents=True, exist_ok=True)
                        print(f"    Created {name} directory: {dir_path}")
                    except Exception as e:
                        print(f"    Failed to create {name} directory: {e}")
            
            # Test API connections
            print(f"\n🌐 Testing API connections...")
            api_results = await self.validator.test_api_connections(config)
            
            if api_results['total_apis'] == 0:
                print("  ⚠️  No API keys configured")
            else:
                print(f"     {api_results['successful']}/{api_results['total_apis']} APIs working")
            
            # Overall status
            print(f"\n   System Readiness Summary:")
            print(f"  Configuration: {'  Valid' if result.is_valid else '  Invalid'}")
            print(f"  Directories: {'  Ready' if not missing_dirs or args.fix_paths else '  Missing'}")
            print(f"  APIs: {'  Ready' if api_results['failed'] == 0 else '⚠️  Some issues'}")
            
            if result.is_valid and (not missing_dirs or args.fix_paths) and api_results['failed'] == 0:
                print("\n🎉 System is ready to run!")
                return 0
            else:
                print("\n⚠️  System has issues that should be addressed")
                return 1
                
        except Exception as e:
            print(f"  System check failed: {e}")
            return 1


async def main():
    """Main entry point for CLI"""
    cli = ConfigCLI()
    return await cli.run()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))