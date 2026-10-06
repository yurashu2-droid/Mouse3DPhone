// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "SpatialPointerCore",
    platforms: [.iOS(.v16), .macOS(.v13)],
    products: [
        .library(name: "SpatialPointerCore", targets: ["SpatialPointerCore"]),
        .executable(name: "PacketFixture", targets: ["PacketFixture"])
    ],
    targets: [
        .target(name: "SpatialPointerCore"),
        .executableTarget(name: "PacketFixture", dependencies: ["SpatialPointerCore"]),
        .testTarget(name: "SpatialPointerCoreTests", dependencies: ["SpatialPointerCore"])
    ]
)
