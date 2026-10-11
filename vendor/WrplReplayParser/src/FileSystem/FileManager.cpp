#include "FileSystem.h"
#include "VROMFs.h"
#include <algorithm>
#include <cctype>


bool FileManager::loadVromfs(std::string &vromfsPath) {

  ZoneScoped;
  auto file = this->getFile(vromfsPath);
  if (!file)
      return false;
  if(holder_dir)
  {

    auto v  = std::make_shared<VROMFs>(vromfsPath, holder_dir); // this automatically loads the data into the holder_dir
    this->loaded_vromfs.push_back(v);
    return true;
  }
  else
  {
    auto v  = std::make_shared<VROMFs>(vromfsPath); // this automatically loads the data into the holder_dir
    holder_dir = v->getDirectory();
    this->loaded_vromfs.push_back(v);
    return true;
  }
}

std::unique_ptr<File> FileManager::getFile(const fs::path &path, bool lower, bool prioritizeVromfs) {
  fs::path to_use;
  if(lower)
  {
    std::string tmp = path.string();
    std::ranges::transform(tmp, tmp.begin(), [](char c) { return ::tolower((unsigned char) c); });
    to_use = fs::path(tmp);
  }
  else
    to_use = path;
  if(prioritizeVromfs)
  {
    auto out = this->loadVromfsFile(to_use);
    if(out)
      return out;
  }
  auto out = this->loadRealFsFile(to_use);
  if(out)
    return out;
  if(!prioritizeVromfs) // only runs if we dont prioritize vromfs, makes sure we dont check twice
  {
    out = this->loadVromfsFile(to_use);
    if(out)
      return out;
  }
  return nullptr;
}

void FileManager::find_vromfs_files_in_folder(std::vector<fs::path> &out_list, const std::string &dir_path) {
  SmartFSHandle directory = getObject(fs::path(dir_path));
  if(!directory || directory->getFSObjectType() != isDirectory)
    return ;
  auto d = directory.asDirectory();
  std::vector<FileIndex *> files;
  d->getFilesInDirectory(files);
  for (auto &f : files)
  {
    out_list.push_back(f->getPath());
  }
}

SmartFSHandle FileManager::getObject(const fs::path& path) {
  SmartFSHandle curr_ptr;
  for(const auto &p : path)
  {
    if(!curr_ptr)
    {
      curr_ptr =  (*holder_dir)[p.string()];
    }
    else
    {
      curr_ptr = curr_ptr[p.string()];
    }
    if (!curr_ptr)
      return nullptr;
  }
  return curr_ptr;
}

std::unique_ptr<File> FileManager::loadRealFsFile(const fs::path &path) {
  std::shared_ptr<HostFileIndex> index;
  if(path.is_absolute())
  {
    if(fs::exists(path)) {
      index = std::make_shared<HostFileIndex>(path);
    }
  }
  if (!index)
    for (auto &mount: this->real_fs_mounts) {
      fs::path p = mount / path;
      if (fs::exists(p)) {
        index = std::make_shared<HostFileIndex>(p);
      }
    }
  // final check, check bin directory
  if(!index && fs::exists(path)) {
    index = std::make_shared<HostFileIndex>(path);
  }
  if (index) {
    return index->getFile(index);
  }
  return nullptr;
}

std::unique_ptr<File> FileManager::loadVromfsFile(const fs::path &path) {
  if (!this->holder_dir)
    return nullptr;
  SmartFSHandle file = getObject(path);
  if(!file || file->getFSObjectType() != isFile)
    return nullptr;
  auto f = file.asFile();
  return f->getFile(f);
}

int FileManager::find_files_in_folder(std::vector<std::string> &out_list, std::string &dir_path,
                                      const char *file_suffix_to_match, bool vromfs, bool realfs, bool subdirs) {
  std::vector<fs::path> paths{};
  this->find_vromfs_files_in_folder(paths, dir_path);
  for (auto &p : paths)
  {
    out_list.push_back(p.string());
  }
  return 1;

}

FileManager file_mgr{};
