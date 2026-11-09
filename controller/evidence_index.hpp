#pragma once
// Bounded, newline-delimited path indices for source-attested native evidence.
// This avoids Windows command-line expansion as a game accumulates hundreds of
// immutable recovery reports. Indexed files are still checked by the original
// discovery/translation verification code before use.
#include <filesystem>
#include <fstream>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>
namespace rd_evidence_index {
namespace fs=std::filesystem;
inline std::vector<fs::path> read(const fs::path& index, std::size_t max_entries=512) {
    std::error_code ec;
    if(!fs::is_regular_file(index,ec)||fs::is_symlink(index,ec)||
       fs::file_size(index,ec)>1024u*1024u||ec)
        throw std::runtime_error("NATIVE_EVIDENCE_INDEX_UNSAFE");
    std::ifstream input(index,std::ios::binary);
    if(!input)throw std::runtime_error("NATIVE_EVIDENCE_INDEX_UNREADABLE");
    std::vector<fs::path> entries;
    std::set<fs::path> unique;
    std::string line;
    while(std::getline(input,line)) {
        if(!line.empty()&&line.back()=='\r')line.pop_back();
        if(line.empty()||line.size()>2048||line.find('\0')!=std::string::npos)
            throw std::runtime_error("NATIVE_EVIDENCE_INDEX_LINE_INVALID");
        fs::path p=fs::u8path(line);
        if(!p.is_absolute()||p.extension()!=".json"||
           !fs::is_regular_file(p,ec)||fs::is_symlink(p,ec)||
           fs::file_size(p,ec)>16u*1024u*1024u||ec)
            throw std::runtime_error("NATIVE_EVIDENCE_INDEX_ENTRY_UNSAFE");
        p=p.lexically_normal();
        if(!unique.insert(p).second)
            throw std::runtime_error("NATIVE_EVIDENCE_INDEX_DUPLICATE");
        entries.push_back(p);
        if(entries.size()>max_entries)
            throw std::runtime_error("NATIVE_EVIDENCE_INDEX_ENTRY_LIMIT");
    }
    if(input.bad())throw std::runtime_error("NATIVE_EVIDENCE_INDEX_IO_ERROR");
    return entries;
}
}
