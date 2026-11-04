// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "PortalMobile",
    platforms: [
        .iOS(.v16),
        .macOS(.v13),
    ],
    products: [
        .library(name: "PortalMobile", targets: ["PortalMobile"]),
    ],
    targets: [
        .target(name: "PortalMobile", path: "Sources/PortalMobile"),
        .testTarget(
            name: "PortalMobileTests",
            dependencies: ["PortalMobile"],
            path: "Tests/PortalMobileTests"
        ),
    ]
)
