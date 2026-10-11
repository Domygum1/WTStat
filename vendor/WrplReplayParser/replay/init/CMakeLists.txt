add_library(INIT
        STATIC
        init.cpp
)


add_library(INIT::INIT ALIAS INIT)

target_link_libraries(INIT
        FS::FS
        dagECS::dagECS
        MPI::MPI
        WTEvents::WTEvents
)

set(INCLUDES
        "${BASE_DIR}/src/include"
        "${BASE_DIR}/replay/include"
)


target_include_directories(INIT
        PUBLIC
        ${INCLUDES}
)

