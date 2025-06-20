# DayZ Admin Tools - XML Tools Package

A collection of Python tools for working with DayZ XML configuration files, including types.xml processing and map group prototypes.

## Overview

The `dayz_admin_tools.xml` package contains specialized modules for processing and manipulating DayZ XML format files. These modules help server administrators work with the various XML configuration files that control server behavior, item spawns, and map features.

This package leverages both standard `ElementTree` and `lxml` (if available) for robust XML processing, with special attention to preserving comments and formatting in DayZ XML files.

## Directory Structure

The XML package is organized into submodules:

- **proto/** - Tools for working with mapgroupproto.xml and related item configuration files
- **types/** - Tools for working with types.xml and related item configuration files