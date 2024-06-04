# - Try to find Zmqpp headers and libraries
#
# Usage of this module as follows:
#
# find_package(Zmqpp)
#
# Variables used by this module, they can change the default behaviour and need
# to be set before calling find_package:
#
# Zmqpp_ROOT_DIR  Set this variable to the root installation of
# Zmqpp if the module has problems finding
# the proper installation path.
#
# Variables defined by this module:
#
# Zmqpp_FOUND              System has Zmqpp libs/headers
# Zmqpp_LIBRARIES          The Zmqpp libraries
# Zmqpp_INCLUDE_DIR        The location of Zmqpp headers
# Zmqpp_VERSION            The version of Zmqpp

find_path(Zmqpp_ROOT_DIR
    NAMES include/zmqpp/zmqpp.hpp
)

message("Zmqpp_ROOT_DIR: ${Zmqpp_ROOT_DIR}")
find_library(Zmqpp_LIBRARY
        NAMES zmqpp libzmqpp
        HINTS ${ZeroMQ_ROOT_DIR}/lib
)

find_path(Zmqpp_INCLUDE_DIR
    NAMES zmqpp/zmqpp.hpp
    HINTS ${Zmqpp_ROOT_DIR}/include
)
message("Zmqpp_ROOT_DIR: ${Zmqpp_ROOT_DIR}")

function(extract_version_value value_name file_name value)
    file(STRINGS ${file_name} val REGEX "${value_name} .")
    string(FIND ${val} " " last REVERSE)
    string(SUBSTRING ${val} ${last} -1 val)
    string(STRIP ${val} val)
    set(${value} ${val} PARENT_SCOPE)
endfunction(extract_version_value)

extract_version_value("ZMQPP_VERSION_MAJOR" ${Zmqpp_INCLUDE_DIR}/zmqpp/zmqpp.hpp MAJOR)
extract_version_value("ZMQPP_VERSION_MINOR" ${Zmqpp_INCLUDE_DIR}/zmqpp/zmqpp.hpp MINOR)
extract_version_value("ZMQPP_VERSION_REVISION" ${Zmqpp_INCLUDE_DIR}/zmqpp/zmqpp.hpp REVISION)

set(Zmqpp_VER "${MAJOR}.${MINOR}.${REVISION}")

# We are using the 2.8.10 signature of find_package_handle_standard_args,
# as that is the version that ParaView 5.1 && VTK 6/7 ship, and inject
# into the CMake module path. This allows our FindModule to work with
# projects that include VTK/ParaView before searching for Remus
include(FindPackageHandleStandardArgs)
find_package_handle_standard_args(
    Zmqpp
    REQUIRED_VARS Zmqpp_LIBRARY Zmqpp_INCLUDE_DIR
    VERSION_VAR Zmqpp_VER
)

set(Zmqpp_FOUND ${ZEROMQ_FOUND})
set(Zmqpp_INCLUDE_DIRS ${Zmqpp_INCLUDE_DIR})
set(Zmqpp_LIBRARIES ${Zmqpp_LIBRARY})
set(Zmqpp_VERSION ${Zmqpp_VER})

mark_as_advanced(
    Zmqpp_ROOT_DIR
    Zmqpp_LIBRARY
    Zmqpp_LIBRARY_DEBUG
    Zmqpp_LIBRARY_RELEASE
    Zmqpp_INCLUDE_DIR
    Zmqpp_VERSION
)