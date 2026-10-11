

#ifndef MYEXTENSION_VROMFS_H
#define MYEXTENSION_VROMFS_H

#include "ioSys/dag_memIo.h"
#include "ioSys/dag_fileIo.h"
#include "FileSystem.h"
#include "zstd.h"
#include "ioSys/dag_dataBlock.h"
#include "ioSys/dag_zstdIo.h"


#define DEOBFUSCATE_ZSTD_DATA obfusc_vrom_data
#define OBFUSCATE_ZSTD_DATA   obfusc_vrom_data

class VROMFs;

#define SIGNATURE_MAX_SIZE (1024)


static const unsigned targetCode = _MAKE4C('PC');
static const unsigned targetCode2[2] = {_MAKE4C('iOS'), _MAKE4C('and')};

static inline bool checkTargetCode(unsigned code) {
  return targetCode == code || targetCode2[0] == code || targetCode2[1] == code;
}


static inline void obfusc_vrom_data(void *data, unsigned data_sz) {
  static const unsigned zstd_xor_p[4] = {0xAA55AA55, 0xF00FF00F, 0xAA55AA55, 0x12481248};

  if (data_sz < 16)
    return;
  unsigned *w = (unsigned *) data;
  w[0] ^= zstd_xor_p[0];
  w[1] ^= zstd_xor_p[1];
  w[2] ^= zstd_xor_p[2];
  w[3] ^= zstd_xor_p[3];
  if (data_sz >= 32) {
    w += (data_sz / 4) - 4;
    w[0] ^= zstd_xor_p[3];
    w[1] ^= zstd_xor_p[2];
    w[2] ^= zstd_xor_p[1];
    w[3] ^= zstd_xor_p[0];
  }
}

struct VirtualRomFsDataHdr {
  unsigned label;
  unsigned target;
  unsigned fullSz;
  unsigned hw32;

  [[nodiscard]] unsigned packedSz() const { return hw32 & 0x3FFFFFFU; }

  [[nodiscard]]bool zstdPacked() const { return (hw32 & 0x40000000U) != 0; }

  [[nodiscard]] bool signedContents() const { return (hw32 & 0x80000000U) != 0; }
};

struct VirtualRomFsExtHdr {
  uint16_t size = 0, flags = 0;
  uint32_t version = 0;
};

class VromfsFile;

class VromfsFileIndex : public FileIndex {
    std::span<char> data{};
    VROMFs *owner;

public:
    ~VromfsFileIndex() override = default;

    VromfsFileIndex(const std::string &name, VROMFs *owner, std::span<char> data) : FileIndex(name), data(data),
        owner(owner) {
    }

    VromfsFileIndex(const fs::path &name, VROMFs *owner, std::span<char> data) : FileIndex(name), data(data),
        owner(owner) {
    }

    std::unique_ptr<File> getFile(std::shared_ptr<FileIndex> ths) override;

    friend VromfsFile;
};

class VromfsFile : public File {
    [[nodiscard]] VromfsFileIndex *asIndex() const {
        return static_cast<VromfsFileIndex *>(index.get());
    }

public:
    explicit VromfsFile(const std::shared_ptr<FileIndex> &index) : File(index) {
        auto as_vf = asIndex();
        f_length = (size_t) as_vf->data.size();
        read_offs = 0;
        vromfsPath = index->getPath().relative_path().parent_path();
    }

  std::span<char> readRaw() override {
      return {asIndex()->data.data(), asIndex()->data.size()};
  }

  void Save(std::ofstream *cb) override;

  bool loadBlk(DataBlock &blk) override;

    const VROMFs *getUnderlyingVromfs() override {
        return asIndex()->owner;
    }

protected:
    int64_t read_impl(void *ptr, size_t length) override;

public:
    ~VromfsFile() override = default;

protected:
  fs::path vromfsPath;
  friend VROMFs;

};

class VROMFs {
public:
    explicit VROMFs(const std::string &fName);

    explicit VROMFs(const std::string &fName, std::shared_ptr<Directory> &dir);

  std::shared_ptr<Directory> getDirectory() {
    if (dir == nullptr) {
      dir = std::make_shared<Directory>(fileName);
    }
    return dir;
  }

  bool parseFileToDatablock(File &file, DataBlock &blk) {
      //auto data = file.readRaw();
      if (file.getExtension() != ".blk") {
      return false;
    }
      LFileGeneralLoadCB rdr{&file};
      return blk.loadFromStream(rdr);
  }

  ~VROMFs() {
    if (dict) {
      ZSTD_freeDDict(dict);
    }
  }

    DBNameMap *getVromfsSharedNameMap() const {
        return this->nm.get();
    }

    ZSTD_DDict_s *getVromfsBlkDDict() const {
        return this->dict;
    }

    //VROMFs(const std::span<char> &data) = 0;

protected:
    bool load_raw_vromfs_data(IGenLoad &reader) {
        //char embedded_md5[16];
    //unsigned char signature[SIGNATURE_MAX_SIZE];
    //int signature_size = 0;
    enum {
      HDR,
      CONTENT,
      MD5,
      ADDITIONAL_CONTENT,
      SIGNATURE
    };
    //const void *buffers[] = {&hdr, nullptr, embedded_md5, nullptr, signature};
    //unsigned buf_sizes[] = {sizeof(hdr), 0, sizeof(embedded_md5), 0, 0};
    void *buf = nullptr;

    std::shared_ptr<std::vector<char>> fs;

    std::ofstream outputFile;

    if (!reader.readInto(hdr))
      goto load_fail;
    fs = std::make_shared<std::vector<char>>(hdr.fullSz);

    if (hdr.label != _MAKE4C('VRFs') && hdr.label != _MAKE4C('VRFx'))
      goto load_fail;
    if (!checkTargetCode(hdr.target))
      goto load_fail;
    /*
    fs = (VirtualRomFsData *)mem->tryAlloc(FS_OFFS + hdr.fullSz);
    if (!fs)
        goto load_fail;
    new (fs, _NEW_INPLACE) VirtualRomFsData();
    fs->mtime = st.mtime;*/

    if (hdr.label == _MAKE4C('VRFx')) {
      if (!reader.readInto(extHdr))
        goto load_fail;
      /*
      if (hdr_ext.size >= sizeof(VirtualRomFsExtHdr))
      {
        fs->flags = hdr_ext.flags;
        fs->version = hdr_ext.version;
      }
      */
      reader.seekrel((int)(extHdr.size - sizeof(extHdr)));
    }

    if (hdr.packedSz()) {
      buf = malloc(hdr.packedSz());
      if (!buf)
        goto load_fail;
      if (!reader.readExact(buf, (int) hdr.packedSz()))
          goto load_fail;

      size_t sz = hdr.fullSz;
      if (hdr.zstdPacked()) {
        obfusc_vrom_data(buf, hdr.packedSz());
        sz = zstd_decompress((unsigned char *) fs->data(), sz, buf, hdr.packedSz());
        if (sz != hdr.fullSz)
          goto load_fail;
        obfusc_vrom_data(buf, hdr.packedSz());
      } else {
        assert(false && "data is zlib compressed!!!!");
      }
    } else {
        if (!reader.readExact(fs->data(), (int) hdr.fullSz))
            goto load_fail;
    }

    raw_data = fs;
    size = hdr.fullSz;
    if (buf)
      free(buf);
    return true;
    load_fail:
    if (buf)
      free(buf);
    return false;
  }

    bool parse_raw_vromfs_data(IGenLoad &reader);

    std::string fileName;
  VirtualRomFsDataHdr hdr{};
  VirtualRomFsExtHdr extHdr;
  std::shared_ptr<std::vector<char>> raw_data;
  unsigned size{};
  std::shared_ptr<Directory> dir;
    std::shared_ptr<DBNameMap> nm;
    ZSTD_DDict_s *dict{};
};


#endif //MYEXTENSION_VROMFS_H