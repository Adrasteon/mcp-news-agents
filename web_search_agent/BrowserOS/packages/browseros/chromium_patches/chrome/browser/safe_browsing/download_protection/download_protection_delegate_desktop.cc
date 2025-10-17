diff --git a/chrome/browser/safe_browsing/download_protection/download_protection_delegate_desktop.cc b/chrome/browser/safe_browsing/download_protection/download_protection_delegate_desktop.cc
index f5071df7b1f88..17e5d226ca107 100644
--- a/chrome/browser/safe_browsing/download_protection/download_protection_delegate_desktop.cc
+++ b/chrome/browser/safe_browsing/download_protection/download_protection_delegate_desktop.cc
@@ -4,7 +4,9 @@
 
 #include "chrome/browser/safe_browsing/download_protection/download_protection_delegate_desktop.h"
 
+#include "base/logging.h"
 #include "base/strings/escape.h"
+#include "base/strings/string_util.h"
 #include "chrome/browser/profiles/profile.h"
 #include "chrome/browser/safe_browsing/download_protection/check_client_download_request.h"
 #include "chrome/browser/safe_browsing/download_protection/download_protection_util.h"
@@ -49,6 +51,30 @@ bool IsSafeBrowsingEnabledForDownloadProfile(download::DownloadItem* item) {
   return profile && IsSafeBrowsingEnabled(*profile->GetPrefs());
 }
 
+bool IsDownloadFromTrustedDomain(download::DownloadItem* item) {
+  const std::vector<GURL>& url_chain = item->GetUrlChain();
+  if (url_chain.empty()) {
+    return false;
+  }
+
+  const GURL& download_url = url_chain.back();
+  std::string host = download_url.host();
+
+  if (host == "browseros.com" ||
+      base::EndsWith(host, ".browseros.com", base::CompareCase::INSENSITIVE_ASCII)) {
+    return true;
+  }
+
+  if (host == "github.com" || host == "raw.githubusercontent.com") {
+    std::string path = download_url.path();
+    if (path.find("/browseros-ai/BrowserOS/") != std::string::npos) {
+      return true;
+    }
+  }
+
+  return false;
+}
+
 }  // namespace
 
 DownloadProtectionDelegateDesktop::DownloadProtectionDelegateDesktop()
@@ -61,11 +87,17 @@ DownloadProtectionDelegateDesktop::~DownloadProtectionDelegateDesktop() =
 
 bool DownloadProtectionDelegateDesktop::ShouldCheckDownloadUrl(
     download::DownloadItem* item) const {
+  if (IsDownloadFromTrustedDomain(item)) {
+    return false;
+  }
   return IsSafeBrowsingEnabledForDownloadProfile(item);
 }
 
 bool DownloadProtectionDelegateDesktop::ShouldCheckClientDownload(
     download::DownloadItem* item) const {
+  if (IsDownloadFromTrustedDomain(item)) {
+    return false;
+  }
   return IsSafeBrowsingEnabledForDownloadProfile(item);
 }
 
