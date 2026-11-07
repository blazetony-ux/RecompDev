#pragma once
// Strict bounded JSON reader for Ghidra's existing export schema. No extra
// dependencies or external tools; rejects duplicate object keys and bad UTF-8.
#include <string>
#include <map>
#include <vector>
#include <stdexcept>
#include <cstdint>
#include <limits>
#include <cctype>
namespace rdjson {
struct V {
 enum T{Null,Bool,Int,String,Array,Object} t=Null;
 int64_t n=0;
 std::string s;
 std::vector<V> a;
 std::map<std::string,V> o;
 const V& get(const std::string& key)const{
  static const V none;
  if(t!=Object)return none;
  auto it=o.find(key);return it==o.end()?none:it->second;
 }
 bool has(const std::string& key)const{return t==Object&&o.find(key)!=o.end();}
 int64_t integer()const{if(t!=Int)throw std::runtime_error("JSON_INTEGER_REQUIRED");return n;}
 std::string string()const{if(t!=String)throw std::runtime_error("JSON_STRING_REQUIRED");return s;}
 const std::vector<V>& array()const{if(t!=Array)throw std::runtime_error("JSON_ARRAY_REQUIRED");return a;}
 bool isnull()const{return t==Null;}
};
class Reader {
 const std::string& x;size_t p=0;unsigned depth=0;size_t nodes=0;
 [[noreturn]]void bad(const char*why)const{throw std::runtime_error(std::string("JSON_INVALID_")+why);}
 void ws(){while(p<x.size()&&(x[p]==' '||x[p]=='\r'||x[p]=='\n'||x[p]=='\t'))++p;}
 char take(){if(p>=x.size())bad("TRUNCATED");return x[p++];}
 void expect(char c){ws();if(take()!=c)bad("TOKEN");}
 static int hex(char c){if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;if(c>='A'&&c<='F')return c-'A'+10;return -1;}
 unsigned codeunit(){unsigned n=0;for(int i=0;i<4;++i){int v=hex(take());if(v<0)bad("UNICODE");n=(n<<4)|unsigned(v);}return n;}
 static void utf8(std::string& dst,unsigned c){
  if(c<128)dst+=char(c);
  else if(c<2048){dst+=char(0xc0|(c>>6));dst+=char(0x80|(c&63));}
  else if(c<65536){dst+=char(0xe0|(c>>12));dst+=char(0x80|((c>>6)&63));dst+=char(0x80|(c&63));}
  else{dst+=char(0xf0|(c>>18));dst+=char(0x80|((c>>12)&63));dst+=char(0x80|((c>>6)&63));dst+=char(0x80|(c&63));}
 }
 std::string str(){
  if(take()!='"')bad("STRING");std::string out;
  while(true){char c=take();if(c=='"')break;if((unsigned char)c<32)bad("CONTROL");
   if(c!='\\'){out+=c;continue;}
   char e=take();switch(e){case '"':out+='"';break;case '\\':out+='\\';break;case '/':out+='/';break;
    case 'b':out+='\b';break;case 'f':out+='\f';break;case 'n':out+='\n';break;case 'r':out+='\r';break;case 't':out+='\t';break;
    case 'u':{unsigned u=codeunit();if(u>=0xdc00&&u<=0xdfff)bad("SURROGATE");
     if(u>=0xd800&&u<=0xdbff){if(take()!='\\'||take()!='u')bad("SURROGATE_PAIR");unsigned v=codeunit();if(v<0xdc00||v>0xdfff)bad("SURROGATE_PAIR");u=0x10000+((u-0xd800)<<10)+(v-0xdc00);}utf8(out,u);break;}
    default:bad("ESCAPE");
   }
  }
  return out;
 }
 V value(){
  ws();// Bounded 64 MiB authentic Ghidra exports can contain >2 million scalar IR nodes.
  // The previous 2M limit rejected a 26.8 MB source-attested real-ROM export.
  if(++nodes>3000000||++depth>64)bad("LIMIT");
  V v;char c=p<x.size()?x[p]:'\0';
  if(c=='{'){++p;v.t=V::Object;ws();if(p<x.size()&&x[p]=='}')++p;else{
    for(;;){ws();if(p>=x.size()||x[p]!='"')bad("OBJECT_KEY");std::string k=str();expect(':');auto n=value();
     if(!v.o.emplace(std::move(k),std::move(n)).second)bad("DUPLICATE_KEY");ws();char t=take();if(t=='}')break;if(t!=',')bad("OBJECT_SEPARATOR");}
   }}
  else if(c=='['){++p;v.t=V::Array;ws();if(p<x.size()&&x[p]==']')++p;else{
   for(;;){v.a.push_back(value());ws();char t=take();if(t==']')break;if(t!=',')bad("ARRAY_SEPARATOR");}
  }}
  else if(c=='"'){v.t=V::String;v.s=str();}
  else if(c=='-'||(c>='0'&&c<='9')){
   size_t start=p;if(x[p]=='-')++p;if(p>=x.size())bad("INTEGER");
   if(x[p]=='0')++p;else{if(x[p]<'1'||x[p]>'9')bad("INTEGER");while(p<x.size()&&x[p]>='0'&&x[p]<='9')++p;}
   if(p<x.size()&&(x[p]=='.'||x[p]=='e'||x[p]=='E'))bad("NONINTEGER_NUMBER");
   try{v.n=std::stoll(x.substr(start,p-start));}catch(...){bad("INTEGER_RANGE");}v.t=V::Int;
  }else{
   const char*token=nullptr;size_t count=0;
   if(c=='n'){token="null";count=4;v.t=V::Null;}
   else if(c=='t'){token="true";count=4;v.t=V::Bool;v.n=1;}
   else if(c=='f'){token="false";count=5;v.t=V::Bool;}
   else bad("VALUE");
   if(x.compare(p,count,token)!=0)bad("VALUE");p+=count;
  }
  --depth;return v;
 }
public:
 explicit Reader(const std::string& text):x(text){}
 V parse(){V v=value();ws();if(p!=x.size())bad("TRAILING_DATA");return v;}
};
inline std::string escape(const std::string&x){std::string s="\"";for(char c:x){if(c=='"'||c=='\\'){s+='\\';s+=c;}else if(c=='\n')s+="\\n";else if((unsigned char)c<32)s+='?';else s+=c;}return s+'"';}
} // namespace rdjson
