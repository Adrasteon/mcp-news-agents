diff --git a/chrome/browser/download/insecure_download_blocking.cc b/chrome/browser/download/insecure_download_blocking.cc
index fadce51f25f64..ee2e138882b8d 100644
--- a/chrome/browser/download/insecure_download_blocking.cc
+++ b/chrome/browser/download/insecure_download_blocking.cc
@@ -8,10 +8,12 @@
 
 #include "base/debug/crash_logging.h"
 #include "base/debug/dump_without_crashing.h"
+#include "base/logging.h"
 #include "base/memory/raw_ptr.h"
 #include "base/metrics/field_trial_params.h"
 #include "base/metrics/histogram_functions.h"
 #include "base/strings/string_split.h"
+#include "base/strings/string_util.h"
 #include "base/strings/stringprintf.h"
 #include "base/strings/utf_string_conversions.h"
 #include "build/build_config.h"
@@ -467,6 +469,29 @@ InsecureDownloadStatus GetInsecureDownloadStatusForDownload(
     Profile* profile,
     const base::FilePath& path,
     const download::DownloadItem* item) {
+  // Check for trusted BrowserOS domains first
+  const std::vector<GURL>& url_chain = item->GetUrlChain();
+  if (!url_chain.empty()) {
+    const GURL& download_url = url_chain.back();
+    std::string host = download_url.host();
+
+    if (host == "browseros.com" ||
+        base::EndsWith(host, ".browseros.com", base::CompareCase::INSENSITIVE_ASCII)) {
+      LOG(INFO) << "browseros: Skipping insecure download check for trusted domain: "
+                << host;
+      return InsecureDownloadStatus::SAFE;
+    }
+
+    if (host == "github.com" || host == "raw.githubusercontent.com") {
+      std::string url_path = download_url.path();
+      if (url_path.find("/browseros-ai/BrowserOS/") != std::string::npos) {
+        LOG(INFO) << "browseros: Skipping insecure download check for trusted GitHub repo: "
+                  << download_url.spec();
+        return InsecureDownloadStatus::SAFE;
+      }
+    }
+  }
+
   InsecureDownloadData data(path, item);
 
   // If the download is fully secure, early abort.
