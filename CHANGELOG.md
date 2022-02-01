# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.1] - 2022-02-01

### Fixed

- Don't send 0 as the response size for streaming responses, send nothing instead.

## [1.2.0] - 2022-01-31

### Added

- Send request and response body size information with metrics.

### Changed

- Change `status_code` into an optional parameter in `ApilyticsSender.set_response_info`.

## [1.1.0] - 2022-01-16

### Added

- Send query parameters in addition to the path.

## [1.0.2] - 2022-01-16

### Added

- Send Apilytics version info together with metrics.

## [1.0.1] - 2022-01-12

### Fixed

- Improve README documentation.

## [1.0.0] - 2022-01-10

### Added

- Initial version with Django and FastAPI support.
