#include "ecs/EntityManager.h"
#include "ecs/ComponentTypesDefs.h"
#include "network/CNetwork.h"
#include "FileSystem.h"
#include "init/initialize.h"
#include "mpi/mpi.h"

#include <ctime>
#include "Replay/Replay.h"
#include "Replay/find_rpl_files.h"
#include "mpi/ObjectDispatcher.h"
#include "Logger.h"

#include "state/ParserState.h"
#include <cctype>

#include <cstdlib>
#include <thread>
#include <barrier>
#include "tracy/Tracy.hpp"



std::string convert_os_path_to_wsl2(std::string &str) { // this function assumes a windows os with a wsl2 linux
  G_ASSERTF(str[1] == ':', "must be an absolute path");
  std::string payload = "/mnt/";
  payload += static_cast<char>(std::tolower(str[0]));
  payload += "/";
  payload += str.substr(3);
  std::replace(payload.begin(), payload.end(), '\\', '/');
  return payload;
}

std::string convert_os_path_to_wsl2(const char *str) {
  std::string t(str);
  return convert_os_path_to_wsl2(t);
}
//#include <sanitizer/asan_interface.h>

//void checkMemory() {
  // Prints all live allocations (with stacks) to stderr
//  __asan_print_accumulated_stats();
//}

int main() {
  //std::signal(SIGSEGV, signal_handler);
  fs::path conf_dir = CONFIG_DIR;
  fs::path config_file = conf_dir / "dagor_replay_test.blk";
  DataBlock conf_blk;
  G_ASSERT(load(conf_blk, config_file.string().c_str()));
  bool is_server_replay = conf_blk.getBool("is_server_replay", false);
  bool source_is_linux_path = conf_blk.getBool("source_is_linux_path", false);
  auto replay_path = conf_blk.getStr("source", nullptr);
  bool bin_is_linux_path = conf_blk.getBool("bin_is_linux_path", false);
  auto bin_path = conf_blk.getStr("bin_path", nullptr);
  std::string rpl_path_str = replay_path;
  std::string bin_path_str = bin_path;
  G_UNUSED(source_is_linux_path);
  G_UNUSED(bin_is_linux_path);
#ifdef _TARGET_PC_LINUX
  if(!source_is_linux_path) {
    rpl_path_str = convert_os_path_to_wsl2(replay_path);
  }
  if(!bin_is_linux_path) {
    bin_path_str = convert_os_path_to_wsl2(bin_path);
  }
#endif
  std::string logfile_str = (conf_dir / "logfile.txt").string();
  initialize(bin_path_str, logfile_str);
  g_log_handler.start_thread();
  //auto t = ecs::g_ecs_data->getTemplateDB()->getTemplate("attachable_wear_fast_sf_helmet_item");
  ServerReplay *srv_rpl = nullptr;
  Replay *rpl = nullptr;
  if (is_server_replay) {
    fs::path t{rpl_path_str};
    srv_rpl = new ServerReplay(t);
  } else {
    rpl = new Replay(rpl_path_str);
  }
  constexpr int num_threads = 20;
  //checkMemory();
  ecs::g_ecs_data->printCurrentMemoryUsage();
  g_log_handler.wait_until_empty();
  g_log_handler.flush_all();

  auto worker = [&](int id) {
    ZoneScopedN("Worker Run");
    ParserState *state_ptr = nullptr;
    IReplayReader *rdr = nullptr;
    //sync_point.arrive_and_wait(); // block until all threads are ready
    std::cout << fmt::format("Thread {} started!\n", id);
    auto start = std::chrono::high_resolution_clock::now();
    {
      ZoneScopedN("Create Reader and State");
      if(is_server_replay) {
        rdr = srv_rpl->getRplReader();
        state_ptr = new ParserState{srv_rpl};
      }
      else {
        rdr = rpl->getFullDecompressReplayReader();
        state_ptr = new ParserState{rpl};
      }
    }


    ParserState &state = *state_ptr;

    auto pkt = ReplayPacket();
    //std::exit(0);
    bool end = false;
    int AircraftCount = 0;
    uint32_t packet_count = 0;
    {
      ZoneScopedN("Parsing");
      while (!end && rdr->getNextPacket(&pkt)) {
        state.curr_time_ms = pkt.timestamp_ms;
        packet_count++;
        if (packet_count == 1500) {
          state.g_entity_mgr.broadcastEventImmediate(ecs::EventEntitySomething{});
        }
        switch (pkt.type) {
          case ReplayPacketType::EndMarker: {
            LOG("Replay Ending at time {}", ((float) pkt.timestamp_ms) / 1000);
            end = true;
            break;
          }
          case ReplayPacketType::StartMarker: {
            LOGD("Replay StartMarker");
            break;
          }
          case ReplayPacketType::AircraftSmall: {
            AircraftCount++;
            break;
          }
          case ReplayPacketType::Chat:
            break;
          case ReplayPacketType::MPI: {
            auto m = mpi::dispatch(pkt.stream, &state, false);
            if (m != nullptr) {
              mpi::send(m);
              delete m;
            }
            break;
          }
          case ReplayPacketType::NextSegment: {
            //LOG("NextSegment");
            break;
          }
          case ReplayPacketType::ECS: {
            state.onPacket(&pkt);
            break;
          }
          case ReplayPacketType::Snapshot: // useless
            break;
          case ReplayPacketType::ReplayHeaderInfo:
            break;
        }
      }
    }

    delete state_ptr;
    delete rdr;
    auto ended = std::chrono::high_resolution_clock::now();

    std::chrono::duration<double, std::milli> duration = ended - start;
    std::cout << fmt::format("thread {} profile time: {}; packet count: {}\n", id, duration.count(), packet_count);
  };
  for(int i = 0; i < 1; i++) {
    {
      std::vector<std::jthread> threads;
      for (int i = 0; i < num_threads; ++i)
        threads.emplace_back(worker, i);
    }
    g_log_handler.wait_until_empty();
    g_log_handler.flush_all();
  }


  delete srv_rpl;
  delete rpl;
  return 0;
}