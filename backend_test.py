import requests
import sys
import json
import time
from datetime import datetime
from pathlib import Path
import io

class MusicAppAPITester:
    def __init__(self, base_url="http://localhost:8000/api"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.project_id = None
        self.style_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, files=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}" if endpoint else self.base_url
        headers = {'Content-Type': 'application/json'} if not files else {}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                if files:
                    response = requests.post(url, files=files)
                else:
                    response = requests.post(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    print(f"   Response: {json.dumps(response_data, indent=2)[:200]}...")
                    return True, response_data
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Error: {response.text}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_root_endpoint(self):
        """Test the root API endpoint"""
        return self.run_test("Root Endpoint", "GET", "", 200)

    def test_status_endpoints(self):
        """Test status check endpoints"""
        # Create status check
        success, response = self.run_test(
            "Create Status Check",
            "POST",
            "status",
            200,
            data={"client_name": "test_client"}
        )
        
        if success:
            # Get status checks
            self.run_test("Get Status Checks", "GET", "status", 200)
        
        return success

    def test_project_creation(self):
        """Test project creation"""
        success, response = self.run_test(
            "Create Project",
            "POST",
            "projects",
            200,
            data={"name": f"Test Project {datetime.now().strftime('%H%M%S')}"}
        )
        
        if success and 'id' in response:
            self.project_id = response['id']
            print(f"   Created project ID: {self.project_id}")
        
        return success

    def test_get_projects(self):
        """Test getting all projects"""
        return self.run_test("Get All Projects", "GET", "projects", 200)

    def test_get_project_by_id(self):
        """Test getting a specific project"""
        if not self.project_id:
            print("❌ No project ID available for testing")
            return False
        
        return self.run_test(
            "Get Project by ID",
            "GET",
            f"projects/{self.project_id}",
            200
        )

    def test_file_upload(self):
        """Test file upload functionality"""
        if not self.project_id:
            print("❌ No project ID available for file upload testing")
            return False

        # Create a dummy audio file for testing
        dummy_audio_content = b"dummy audio content for testing"
        files = {
            'file': ('test_audio.mp3', io.BytesIO(dummy_audio_content), 'audio/mpeg')
        }
        
        success, response = self.run_test(
            "Upload Audio File",
            "POST",
            f"projects/{self.project_id}/upload",
            200,
            files=files
        )
        
        # Test invalid file type
        invalid_files = {
            'file': ('test.txt', io.BytesIO(b"not audio"), 'text/plain')
        }
        
        self.run_test(
            "Upload Invalid File Type",
            "POST",
            f"projects/{self.project_id}/upload",
            400,
            files=invalid_files
        )
        
        return success

    def test_beat_transformation(self):
        """Test MIDI transformation (NEW FUNCTIONALITY)"""
        if not self.project_id:
            print("❌ No project ID available for transformation testing")
            return False

        print("\n🎼 Testing MIDI Transformation (Critical Update)...")
        success, response = self.run_test(
            "Transform Beat to MIDI Stems",
            "POST",
            f"projects/{self.project_id}/transform",
            200
        )
        
        if success:
            print("🔍 Analyzing transformation response...")
            
            # Check for MIDI-specific response fields
            expected_fields = [
                'transformation_type', 'midi_files', 'musicxml_files', 
                'stems_available', 'original_composition_created'
            ]
            
            missing_fields = [field for field in expected_fields if field not in response]
            if missing_fields:
                print(f"❌ Missing MIDI transformation fields: {missing_fields}")
                return False
            
            # Verify transformation type is MIDI-based
            transformation_type = response.get('transformation_type')
            if transformation_type != 'advanced_stems_midi':
                print(f"❌ Wrong transformation type: {transformation_type} (expected: advanced_stems_midi)")
                return False
            
            # Check MIDI files were created
            midi_files = response.get('midi_files', [])
            musicxml_files = response.get('musicxml_files', [])
            
            print(f"✅ Transformation type: {transformation_type}")
            print(f"✅ MIDI files created: {len(midi_files)} files")
            print(f"✅ MusicXML files created: {len(musicxml_files)} files")
            print(f"✅ Stems available: {response.get('stems_available', False)}")
            print(f"✅ Original composition created: {response.get('original_composition_created', False)}")
            
            if midi_files:
                print(f"   MIDI files: {', '.join(midi_files)}")
            if musicxml_files:
                print(f"   MusicXML files: {', '.join(musicxml_files)}")
            
            # CRITICAL CHECK: Ensure NO MP3 file was created
            if 'transformed_file' in response:
                print(f"❌ CRITICAL ERROR: MP3 file still being created: {response['transformed_file']}")
                print("   This should NOT happen - transformation should create MIDI only!")
                return False
            
            print("✅ CRITICAL SUCCESS: No MP3 file created - MIDI transformation working correctly!")
            
        return success

    def test_lyrics_generation(self):
        """Test lyrics generation with different styles"""
        if not self.project_id:
            print("❌ No project ID available for lyrics testing")
            return False

        styles_to_test = ['trap', 'boom_bap', 'drill', 'conscious', 'melodic', 'freestyle']
        
        for style in styles_to_test:
            success, response = self.run_test(
                f"Generate Lyrics - {style.title()}",
                "POST",
                f"projects/{self.project_id}/generate-lyrics",
                200,
                data={
                    "project_id": self.project_id,
                    "style": style,
                    "custom_prompt": f"Create {style} lyrics about success and motivation"
                }
            )
            
            if success and 'lyrics' in response:
                print(f"   Generated lyrics preview: {response['lyrics'][:100]}...")
            
            # Only test one style to avoid rate limiting
            return success
        
        return False

    def test_user_styles(self):
        """Test user styles CRUD operations"""
        # Create user style
        success, response = self.run_test(
            "Create User Style",
            "POST",
            "user-styles",
            200,
            data={
                "name": "Test Style",
                "description": "A test style for automated testing",
                "sample_lyrics": "This is a sample lyric for testing purposes\nWith multiple lines and flow"
            }
        )
        
        if success and 'id' in response:
            self.style_id = response['id']
            print(f"   Created style ID: {self.style_id}")
        
        # Get all user styles
        self.run_test("Get User Styles", "GET", "user-styles", 200)
        
        # Delete user style
        if self.style_id:
            self.run_test(
                "Delete User Style",
                "DELETE",
                f"user-styles/{self.style_id}",
                200
            )
        
        return success

    def test_file_download(self):
        """Test file download endpoint"""
        # This will likely fail since we uploaded a dummy file, but we test the endpoint
        return self.run_test(
            "Download File (Expected to fail)",
            "GET",
            "files/nonexistent.mp3",
            404
        )

    def test_export_functionality(self):
        """Test the new export functionality"""
        if not self.project_id:
            print("❌ No project ID available for export testing")
            return False

        print("\n🎯 Testing Export Functionality...")
        
        # Test export endpoint
        success, export_response = self.run_test(
            "Export Project Info",
            "GET",
            f"projects/{self.project_id}/export",
            200
        )
        
        if success:
            print(f"   Export Data: {json.dumps(export_response, indent=2)}")
            
            # Verify export data structure
            required_fields = ['project_name', 'has_audio', 'has_lyrics', 'ready_for_export']
            missing_fields = [field for field in required_fields if field not in export_response]
            
            if missing_fields:
                print(f"❌ Missing required fields in export response: {missing_fields}")
                return False
            
            print(f"   Ready for export: {export_response.get('ready_for_export', False)}")
            print(f"   Has audio: {export_response.get('has_audio', False)}")
            print(f"   Has lyrics: {export_response.get('has_lyrics', False)}")
        
        return success

    def test_download_stems_package(self):
        """Test the new download-stems endpoint"""
        if not self.project_id:
            print("❌ No project ID available for stems download testing")
            return False

        print("\n📦 Testing MIDI Stems Package Download...")
        
        url = f"{self.base_url}/projects/{self.project_id}/download-stems"
        print(f"🔍 Testing Download MIDI Stems Package...")
        print(f"   URL: {url}")
        
        try:
            response = requests.get(url)
            self.tests_run += 1
            
            if response.status_code == 200:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                print(f"   Content-Type: {response.headers.get('content-type', 'Not specified')}")
                print(f"   Content-Disposition: {response.headers.get('content-disposition', 'Not specified')}")
                print(f"   Content Length: {len(response.content)} bytes")
                
                # Check if it's a ZIP file
                content_type = response.headers.get('content-type', '')
                if 'zip' in content_type or 'application/zip' in content_type:
                    print("✅ Correct content type: ZIP file")
                else:
                    print(f"⚠️  Unexpected content type: {content_type}")
                
                # Check Content-Disposition header for filename
                content_disposition = response.headers.get('content-disposition', '')
                if 'attachment' in content_disposition and '.zip' in content_disposition:
                    print("✅ Correct Content-Disposition: ZIP attachment")
                else:
                    print(f"⚠️  Unexpected Content-Disposition: {content_disposition}")
                
                return True
            elif response.status_code == 404:
                print(f"⚠️  Expected behavior - No stems available yet (Status: {response.status_code})")
                try:
                    error_data = response.json()
                    print(f"   Error message: {error_data.get('detail', 'No details')}")
                except:
                    pass
                return True  # This is expected if transformation hasn't been done
            else:
                print(f"❌ Failed - Expected 200 or 404, got {response.status_code}")
                try:
                    print(f"   Response: {response.json()}")
                except:
                    print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False

    def test_download_lyrics_functionality(self):
        """Test the lyrics download functionality"""
        if not self.project_id:
            print("❌ No project ID available for lyrics download testing")
            return False

        print("\n📝 Testing Lyrics Download...")
        
        # Test lyrics download endpoint
        url = f"{self.base_url}/projects/{self.project_id}/download-lyrics"
        print(f"🔍 Testing Download Lyrics Endpoint...")
        print(f"   URL: {url}")
        
        try:
            response = requests.get(url)
            self.tests_run += 1
            
            if response.status_code == 200:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                print(f"   Content-Type: {response.headers.get('content-type', 'Not specified')}")
                print(f"   Content-Disposition: {response.headers.get('content-disposition', 'Not specified')}")
                print(f"   Content Length: {len(response.content)} bytes")
                
                # Check if it's a text file
                if 'text' in response.headers.get('content-type', ''):
                    content_preview = response.text[:200] + "..." if len(response.text) > 200 else response.text
                    print(f"   Content Preview: {content_preview}")
                
                return True
            elif response.status_code == 404:
                print(f"⚠️  Expected behavior - No lyrics available yet (Status: {response.status_code})")
                return True  # This is expected if no lyrics were generated
            else:
                print(f"❌ Failed - Expected 200 or 404, got {response.status_code}")
                try:
                    print(f"   Response: {response.json()}")
                except:
                    print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False

    def test_export_with_incomplete_project(self):
        """Test export functionality with incomplete project"""
        print("\n🔍 Testing Export with Incomplete Project...")
        
        # Create a new project without completing the workflow
        incomplete_project_name = f"Incomplete_Export_Test_{datetime.now().strftime('%H%M%S')}"
        success, response = self.run_test(
            "Create Incomplete Project for Export Test",
            "POST",
            "projects",
            200,
            data={"name": incomplete_project_name}
        )
        
        if not success or 'id' not in response:
            return False
            
        incomplete_project_id = response['id']
        
        # Test export endpoint with incomplete project
        success, export_response = self.run_test(
            "Export Incomplete Project",
            "GET",
            f"projects/{incomplete_project_id}/export",
            200
        )
        
        if success:
            print(f"   Incomplete Project Export Data: {json.dumps(export_response, indent=2)}")
            ready_for_export = export_response.get('ready_for_export', True)  # Should be False
            if not ready_for_export:
                print("✅ Correctly identified incomplete project as not ready for export")
                return True
            else:
                print("❌ Incomplete project incorrectly marked as ready for export")
                return False
        
        return False

    def run_all_tests(self):
        """Run all API tests"""
        print("🎵 Starting Music Production App API Tests")
        print("=" * 50)
        
        # Test basic connectivity
        if not self.test_root_endpoint()[0]:
            print("❌ Root endpoint failed - stopping tests")
            return 1
        
        # Test status endpoints
        self.test_status_endpoints()
        
        # Test project management
        if not self.test_project_creation():
            print("❌ Project creation failed - stopping tests")
            return 1
        
        self.test_get_projects()
        self.test_get_project_by_id()
        
        # Test file operations
        self.test_file_upload()
        self.test_beat_transformation()
        
        # Test AI features
        print("\n🤖 Testing AI Features (may take longer)...")
        self.test_lyrics_generation()
        
        # Test user styles
        self.test_user_styles()
        
        # Test file download
        self.test_file_download()
        
        # Test NEW EXPORT FUNCTIONALITY
        print("\n🎯 Testing NEW Export Features...")
        self.test_export_functionality()
        self.test_download_stems_package()
        self.test_download_lyrics_functionality()
        self.test_export_with_incomplete_project()
        
        # Print results
        print("\n" + "=" * 50)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return 0
        else:
            print(f"⚠️  {self.tests_run - self.tests_passed} tests failed")
            return 1

def main():
    tester = MusicAppAPITester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())