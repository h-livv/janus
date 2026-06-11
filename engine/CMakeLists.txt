cmake_minimum_required(VERSION 3.16...3.27)

#----------------------------------------------------------------------------
# Project definition
#----------------------------------------------------------------------------

project(Janus)

#----------------------------------------------------------------------------
# Find Geant4 package
#----------------------------------------------------------------------------

find_package(Geant4 REQUIRED ui_all vis_all)

#----------------------------------------------------------------------------
# Include Geant4 use file
#----------------------------------------------------------------------------

include(${Geant4_USE_FILE})

#----------------------------------------------------------------------------
# Project include directories
#----------------------------------------------------------------------------

include_directories(${PROJECT_SOURCE_DIR}/include)

#----------------------------------------------------------------------------
# Locate source and header files
#----------------------------------------------------------------------------

file(GLOB JANUS_SOURCES
    ${PROJECT_SOURCE_DIR}/src/*.cc
)

file(GLOB JANUS_HEADERS
    ${PROJECT_SOURCE_DIR}/include/*.hh
)

#----------------------------------------------------------------------------
# Create executable
#----------------------------------------------------------------------------

add_executable(janus
    janus.cc
    ${JANUS_SOURCES}
    ${JANUS_HEADERS}
)

#----------------------------------------------------------------------------
# Link Geant4 libraries
#----------------------------------------------------------------------------

target_link_libraries(janus
    ${Geant4_LIBRARIES}
)

#----------------------------------------------------------------------------
# Copy macro files into build directory
#----------------------------------------------------------------------------

set(JANUS_MACROS
    macros/init_vis.mac
    macros/run.mac
    macros/vis.mac
)

foreach(_macro ${JANUS_MACROS})

    configure_file(
        ${PROJECT_SOURCE_DIR}/${_macro}
        ${PROJECT_BINARY_DIR}/${_macro}
        COPYONLY
    )

endforeach()

#----------------------------------------------------------------------------
# Optional: install target
#----------------------------------------------------------------------------

install(TARGETS janus DESTINATION bin)